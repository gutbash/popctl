// popctl.asi - population control for GTA IV: The Complete Edition (1.2.0.59).
//
// Ambient population on 1.2.0.59, as measured by hooking the one function every ped removal goes
// through (CPopulation::RemovePed, RVA 0x73BCD0) and logging each deletion's caller, distance and
// visibility - see TraceRemovals:
//
//   * Peds beyond ~30 m are not CPeds. They are 944-byte "far ped" entities (entity type 6) in a
//     second pool of 150 (RVA 0x14B6F10), swapped for a CPed (pool 0x14B6F1C, 120 x 0xEF0) as you
//     approach and back as you leave. Both pools are walked by the same population code.
//   * When the far pool has under 12 free slots, 0x738430 deletes the farthest ones, up to 20 per
//     frame, with no visibility test. On a busy street the pool is full nearly all the time, so that
//     is what cuts the crowd off - on the stock game 4,426 of 8,129 removals, 2,847 of them on camera
//     at a median 74 m. Fix: replace that cull with one that never takes a ped the camera can see.
//   * The shared band test 0x737240 culls past 115 m regardless of visibility (x1.5 for peds the
//     engine flagged as seen), and 70-115 m for off-camera never-flagged peds, after a 2.5-3.5 s
//     timer. Plain data floats at RVA 0xC45994 / 0xC45990.
//   * 0x73AF50 (CPeds) and 0x738620 (far peds) delete off-camera peds immediately past 80 m (seen
//     flag) or 15 m. The constants are shared const-pool floats, so the comiss displacements at
//     0x73B04B / 0x73B054 / 0x738700 are repointed at floats inside this DLL. This was popctl 0.1's
//     only ped patch; it never touched a ped you could see, which is why 0.1 looked like it did nothing.
//   * Spawns per frame: data global 0xC4594C (stock 8), at most 16 candidates are gathered.
//   * Vehicle population statics ([Pokes]): the CVehiclePopulation block at RVA 0xC3FF60.
//
// Nothing on disk is modified; every patch is made in memory, at runtime, after verifying the bytes it
// expects. Any site that does not read its stock value is left alone and logged, so a different game
// build is a no-op rather than a crash. Log: popctl.log next to the .asi.
//
// Engine audio wave slots are NOT here. That is revd's job: https://github.com/gutbash/revd
//
// MIT licensed. See LICENSE.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <math.h>
#include <stdlib.h>

static const DWORD kSiteFar  = 0x73B04B;   // comiss xmm0, [6400.0f]
static const DWORD kSiteNear = 0x73B054;   // comiss xmm0, [225.0f]
static const DWORD kConstFarRva  = 0xBE8CA4;   // 6400.0f in the const pool
static const DWORD kConstNearRva = 0xBE8C00;   // 225.0f
// bytes around the sites, displacement wildcarded:
// f3 0f 10 44 24 0c 84 c0 74 09 0f 2f 05 ?? ?? ?? ?? eb 07 0f 2f 05 ?? ?? ?? ?? 76 18
static const BYTE kSig[] = { 0xf3,0x0f,0x10,0x44,0x24,0x0c, 0x84,0xc0, 0x74,0x09, 0x0f,0x2f,0x05 };
static const DWORD kSigRva = 0x73B041;

static float g_far = 6400.0f, g_near = 225.0f;   // squared metres, the live values the game compares
static char g_log[MAX_PATH], g_ini[MAX_PATH];
static float g_cfgFar = 80.0f, g_cfgNear = 15.0f;

static void Log(const char* fmt, ...);
static const DWORD kSpawnsPerFrameRva = 0xC4594C;
static int g_cfgSpawns = 8;
static BYTE* g_base;              // GTAIV.exe image base
static HMODULE g_self = nullptr;  // this DLL

// The far-ped pool. Ambient peds beyond ~30 m are not CPeds: they live in a second pool of 944-byte
// entities (type 6, same models) and are converted to a full CPed as you approach. Stock size 150.
// When fewer than 12 slots are free, 0x738430 deletes the farthest ones in batches of up to 20 per
// frame with no visibility test - that is the vanishing crowd. Measured 2026-09-15: the pool sat at
// 138-150 for an entire run and 4,426 of 8,129 removals came from that one path, 2,847 of them on
// camera at a median 74 m.
//
// Growing the pool was tried first and abandoned: every far ped also draws a record from a pool
// sized 120+150 (RVA 0x14B6F14, null written through at 0x74CFD9) and a physics instance at +0x78
// from a third (null read at 0x755E90). Each one found was one more crash. Instead the pool-full
// cull is replaced by one with the same budget that deletes off-camera peds first, and deletes
// nothing on camera: if every far ped is in view the pool simply stays full and spawning pauses,
// which the spawner already handles (it checks free slots before creating).
static const DWORD kFarPoolPtrRva = 0x14B6F10;
static const DWORD kPedPoolPtrRva = 0x14B6F1C;
static const DWORD kPoolFullRva = 0x738430;    // void __cdecl PoolFullCull(const float* centre)
static const BYTE  kPoolFullSig[] = { 0x81,0xec,0xb0,0x00,0x00,0x00, 0xa1 };   // sub esp,0xB0; mov eax,[cookie]
static const DWORD kCookieRva = 0xC57FB4;      // the operand of that mov, relocated with the image
static const DWORD kRemovePedFnRva = 0x73BCD0;  // void __cdecl RemovePed(CEntity*, bool)
static const DWORD kIsOnScreenRva = 0x631B10;   // bool __thiscall (bool)
static const int   kPoolFullKeepFree = 12;
static const int   kPoolFullMaxPerFrame = 20;

// Distance band shared by both pools (0x737240): a ped past VisibleKeepMetres is culled whether or
// not you can see it (x1.5 for peds flagged as seen); one between HiddenKeepMetres and that, that the
// camera cannot see and that was never flagged, is culled too. Both after a 2.5-3.5 s grace timer.
// Plain data floats in the CPopulation tunables block, so a value write is enough.
static const DWORD kVisibleKeepRva = 0xC45994;   // 115.0f
static const DWORD kHiddenBandRva  = 0xC45990;   // 70.0f
static const DWORD kFarPoolNearSiteRva = 0x738700;   // comiss xmm2, [225.0f] in the far pool's off-camera cull
static float g_cfgVisible = 130.0f;

// [Pokes] name = RVA,type,stock,new  - plain data globals. type f = float, i = int32, c = 32-bit
// immediate inside an instruction. The write happens only when the global still holds the stock value,
// so a build drift leaves the game untouched and says so in the log.
struct Poke { char name[32]; DWORD rva; char type; float fstock, fnew; int istock, inew; bool done, warned; };
static Poke g_pokes[32];
static int g_nPokes;

static void LoadPokes()
{
    char buf[4096];
    DWORD n = GetPrivateProfileSectionA("Pokes", buf, sizeof buf, g_ini);
    for (char* l = buf; *l && l < buf + n; l += strlen(l) + 1) {
        char* eq = strchr(l, '='); if (!eq || g_nPokes >= 32) continue;
        *eq = 0; char* v = eq + 1;
        Poke& k = g_pokes[g_nPokes];
        strncpy(k.name, l, 31); k.name[31] = 0;
        for (char* t = k.name + strlen(k.name); t > k.name && t[-1] == ' '; --t) t[0] = 0;
        char type = 0; char a[64], b[64];
        if (sscanf(v, " %x , %c , %63[^,] , %63s", &k.rva, &type, a, b) != 4) { Log("pokes: cannot parse '%s=%s'", k.name, v); continue; }
        k.type = type;
        if (type == 'f') { k.fstock = (float)atof(a); k.fnew = (float)atof(b); }
        else if (type == 'i' || type == 'c') { k.istock = atoi(a); k.inew = atoi(b); }
        else { Log("pokes: %s: type must be f, i or c", k.name); continue; }
        g_nPokes++;
    }
}

static void ApplyPokes(BYTE* base)
{
    for (int i = 0; i < g_nPokes; i++) {
        Poke& k = g_pokes[i];
        BYTE* p = base + k.rva;
        MEMORY_BASIC_INFORMATION mbi;
        if (!VirtualQuery(p, &mbi, sizeof mbi) || !(mbi.State & MEM_COMMIT)) { Log("poke %s: RVA %X not committed", k.name, k.rva); continue; }
        if (k.type == 'f') {
            float cur = *(float*)p;
            if (cur == k.fnew) { k.done = true; continue; }
            if (cur != k.fstock) { if (!k.warned) { k.warned = true; Log("poke %s: RVA %X reads %g, expected stock %g - waiting", k.name, k.rva, cur, k.fstock); } continue; }
            if (k.done) continue;
            DWORD old; if (!VirtualProtect(p, 4, PAGE_READWRITE, &old)) { Log("poke %s: VirtualProtect failed", k.name); continue; }
            *(float*)p = k.fnew; VirtualProtect(p, 4, old, &old); k.done = true;
            Log("poke %s: RVA %X %g -> %g", k.name, k.rva, k.fstock, k.fnew);
        } else if (k.type == 'c') {
            int cur = *(int*)p;
            if (cur == k.inew) { k.done = true; continue; }
            if (cur != k.istock) { if (!k.warned) { k.warned = true; Log("poke %s: RVA %X reads %d, expected stock %d - waiting", k.name, k.rva, cur, k.istock); } continue; }
            DWORD old; if (!VirtualProtect(p, 4, PAGE_EXECUTE_READWRITE, &old)) { Log("poke %s: VirtualProtect failed", k.name); continue; }
            *(int*)p = k.inew; VirtualProtect(p, 4, old, &old); FlushInstructionCache(GetCurrentProcess(), p, 4); k.done = true;
            Log("poke %s: code imm at RVA %X %d -> %d", k.name, k.rva, k.istock, k.inew);
        } else {
            int cur = *(int*)p;
            if (cur == k.inew) { k.done = true; continue; }
            if (cur != k.istock) { if (!k.warned) { k.warned = true; Log("poke %s: RVA %X reads %d, expected stock %d - waiting", k.name, k.rva, cur, k.istock); } continue; }
            if (k.done) continue;
            DWORD old; if (!VirtualProtect(p, 4, PAGE_READWRITE, &old)) { Log("poke %s: VirtualProtect failed", k.name); continue; }
            *(int*)p = k.inew; VirtualProtect(p, 4, old, &old); k.done = true;
            Log("poke %s: RVA %X %d -> %d", k.name, k.rva, k.istock, k.inew);
        }
    }
}

static bool PatchSpawns(BYTE* base)
{
    int* p = (int*)(base + kSpawnsPerFrameRva);
    MEMORY_BASIC_INFORMATION mbi;
    if (!VirtualQuery(p, &mbi, sizeof mbi) || !(mbi.State & MEM_COMMIT)) { Log("spawns: global not committed"); return false; }
    if (*p != 8) { Log("spawns: RVA %X reads %d, expected stock 8 - not touched", kSpawnsPerFrameRva, *p); return false; }
    DWORD old;
    if (!VirtualProtect(p, 4, PAGE_READWRITE, &old)) { Log("spawns: VirtualProtect failed %lu", GetLastError()); return false; }
    *p = g_cfgSpawns;
    VirtualProtect(p, 4, old, &old);
    Log("spawns: per-frame ambient spawn cap %d -> %d", 8, g_cfgSpawns);
    return true;
}

static void Log(const char* fmt, ...)
{
    FILE* f = fopen(g_log, "a"); if (!f) return;
    SYSTEMTIME st; GetLocalTime(&st);
    fprintf(f, "[%02d:%02d:%02d.%03d] ", st.wHour, st.wMinute, st.wSecond, st.wMilliseconds);
    va_list ap; va_start(ap, fmt); vfprintf(f, fmt, ap); va_end(ap);
    fputc('\n', f); fclose(f);
}

// Writes a float data global if it still holds its stock value; says so if it does not.
static bool PokeFloat(BYTE* base, DWORD rva, float stock, float val, const char* name)
{
    float* p = (float*)(base + rva);
    MEMORY_BASIC_INFORMATION mbi;
    if (!VirtualQuery(p, &mbi, sizeof mbi) || !(mbi.State & MEM_COMMIT)) { Log("%s: RVA %X not committed", name, rva); return false; }
    if (*p == val) return true;
    if (*p != stock) { Log("%s: RVA %X reads %g, expected stock %g - not touched", name, rva, *p, stock); return false; }
    DWORD old;
    if (!VirtualProtect(p, 4, PAGE_READWRITE, &old)) { Log("%s: VirtualProtect failed %lu", name, GetLastError()); return false; }
    *p = val; VirtualProtect(p, 4, old, &old);
    Log("%s: RVA %X %g -> %g m", name, rva, stock, val);
    return true;
}

// Grows the far-ped pool by rewriting the four size immediates in its constructor. Must run before
// the game constructs its pools, so it is called straight from DllMain; the worker later reads the
// live pool header and reports whether the size took.
struct GamePool { BYTE* storage; BYTE* flags; int size; int elem; int lastFree; int used; };
static int g_cfgFarPool = 150, g_cfgVehPool = 140;
static const int kFarPoolStock = 150, kPedPoolStock = 120, kVehPoolStock = 140;

static void ReportPools(BYTE* base)
{
    GamePool* fp = *(GamePool**)(base + kFarPoolPtrRva);
    GamePool* pp = *(GamePool**)(base + kPedPoolPtrRva);
    GamePool* rp = *(GamePool**)(base + 0x14B6F14);
    if (!fp || !pp || !rp) { Log("pools: not created yet"); return; }
    Log("pools: peds %d x %d bytes, far peds %d x %d bytes, ped records %d x %d bytes%s", pp->size, pp->elem, fp->size, fp->elem, rp->size, rp->elem,
        (fp->size == g_cfgFarPool && rp->size == pp->size + fp->size) ? "" : " - SIZES DID NOT TAKE (pools created before popctl loaded?)");
}

// ---- pool growth ------------------------------------------------------------------------------
// FarPedPool grows the far-ped pool and every pool sized to it. Found by enumerating the game's pool
// constructors (two templates, 46 named pools) and by two crashes: the record pool is exactly
// 120 + 150, and the CAnimBlender / CDummyTask / Event pools are exactly 300 with the animation
// pools at multiples of 300. All are size immediates written before the game constructs anything.
// Every immediate is verified against its stock value first; if any one fails, none are written.
struct ImmPatch { const char* name; DWORD rva; DWORD stock; DWORD val; };
static ImmPatch g_imm[24]; static int g_nImm;
static void AddImm(const char* name, DWORD rva, DWORD stock, DWORD val) { if (g_nImm < 24) { ImmPatch& p = g_imm[g_nImm++]; p.name = name; p.rva = rva; p.stock = stock; p.val = val; } }

static bool PatchPools(BYTE* base)
{
    if (g_cfgFarPool == kFarPoolStock && g_cfgVehPool == kVehPoolStock) return true;
    const DWORD far_ = g_cfgFarPool, rec = kPedPoolStock + far_;
    // the vehicle pool is a named pool with one immediate; no dependents found yet (tested to 200)
    if (g_cfgVehPool != kVehPoolStock) AddImm("Vehicles", 0x64A849, kVehPoolStock, g_cfgVehPool);
    if (g_cfgFarPool != kFarPoolStock) {
    // the two template constructors: alloc bytes, push n, mov [+8] n, cmp n
    AddImm("far pool bytes", 0x1C41FD, kFarPoolStock * 0x3B0, far_ * 0x3B0);
    AddImm("far pool", 0x1C4210, kFarPoolStock, far_); AddImm("far pool", 0x1C4221, kFarPoolStock, far_); AddImm("far pool", 0x1C4250, kFarPoolStock, far_);
    AddImm("ped records bytes", 0x1C3F8D, 270 * 0x190, rec * 0x190);
    AddImm("ped records", 0x1C3FA0, 270, rec); AddImm("ped records", 0x1C3FB1, 270, rec); AddImm("ped records", 0x1C3FE0, 270, rec);
    // named pools sized to the ped count, scaled by (120 + far) / 270
    struct { const char* name; DWORD rva; DWORD stock; } named[] = {
        { "CAnimBlender", 0x7567E9, 300 }, { "CDummyTask", 0x93A506, 300 }, { "Event", 0x74AF26, 300 },
        { "CAtdNodeAnimPlayer", 0x756869, 1500 }, { "crExpressionProcessor", 0x7568A6, 1500 },
        { "crFrameFilterBoneAnalogue", 0x7568E6, 1500 }, { "crmtObserver", 0x756966, 1500 },
        { "crFrameFilterBoneMask", 0x756926, 1800 }, { "CAtdNodeAnimChangePooledObject", 0x756826, 3000 },
        { "CAtdNodeFrameAddress", 0x554146, 21000 },
    };
    for (size_t i = 0; i < sizeof named / sizeof named[0]; i++)
        AddImm(named[i].name, named[i].rva, named[i].stock, (named[i].stock * rec + 269) / 270);
    }
    // verify everything before writing anything
    for (int i = 0; i < g_nImm; i++) {
        BYTE* p = base + g_imm[i].rva;
        MEMORY_BASIC_INFORMATION mbi;
        if (!VirtualQuery(p, &mbi, sizeof mbi) || !(mbi.State & MEM_COMMIT) || (mbi.Protect & (PAGE_NOACCESS | PAGE_GUARD))) { Log("pools: %s at RVA %X not readable - nothing grown", g_imm[i].name, g_imm[i].rva); return false; }
        if (*(DWORD*)p != g_imm[i].stock) { Log("pools: %s at RVA %X reads %u, expected %u - nothing grown", g_imm[i].name, g_imm[i].rva, *(DWORD*)p, g_imm[i].stock); return false; }
        if (p[-1] != 0x68 && !(g_imm[i].rva >= 0x1C3F00 && g_imm[i].rva < 0x1C4300)) { Log("pools: %s at RVA %X is not a push - nothing grown", g_imm[i].name, g_imm[i].rva); return false; }
    }
    for (int i = 0; i < g_nImm; i++) {
        BYTE* p = base + g_imm[i].rva;
        DWORD old;
        if (!VirtualProtect(p, 4, PAGE_EXECUTE_READWRITE, &old)) { Log("pools: VirtualProtect failed at RVA %X", g_imm[i].rva); return false; }
        *(DWORD*)p = g_imm[i].val; VirtualProtect(p, 4, old, &old);
        FlushInstructionCache(GetCurrentProcess(), p, 4);
        if (i == 0 || strcmp(g_imm[i].name, g_imm[i - 1].name) != 0) Log("pools: %s %u -> %u", g_imm[i].name, g_imm[i].stock, g_imm[i].val);
    }
    return true;
}

// ---- the pool-full cull, replaced ------------------------------------------------------------
// Same contract as 0x738430: called once per frame from CPopulation::Process with the population
// centre, frees enough far-pool slots to leave kPoolFullKeepFree, at most kPoolFullMaxPerFrame per
// frame, farthest first. The one change: a ped the camera can see is never a candidate.
static __declspec(noinline) int EntityOnScreen(BYTE* self)
{
    BYTE r = 0; DWORD fn = (DWORD)(g_base + kIsOnScreenRva);
    __asm {
        mov ecx, self
        push 1
        call fn
        mov r, al
    }
    return r;
}

static DWORD g_pfCalls, g_pfDeleted, g_pfSpared;   // for the log line at exit and the trace

static void __cdecl PoolFullCull(const float* centre)
{
    __try {
        GamePool* pool = *(GamePool**)(g_base + kFarPoolPtrRva);
        if (!pool || !pool->storage) return;
        int freeSlots = pool->size - pool->used;
        if (freeSlots >= kPoolFullKeepFree) return;
        int want = kPoolFullKeepFree - freeSlots;
        if (want > kPoolFullMaxPerFrame) want = kPoolFullMaxPerFrame;
        g_pfCalls++;

        // every live, removable far ped with its squared distance from the centre
        struct Cand { float d2; BYTE* ent; };
        Cand cand[1024];
        int n = 0;
        for (int i = 0; i < pool->size && n < 1024; i++) {
            if (pool->flags[i] & 0x80) continue;
            BYTE* ent = pool->storage + (size_t)i * pool->elem;
            BYTE* intel = *(BYTE**)(ent + 0x6C);
            if (intel && intel[0xE]) continue;          // the original skips these too
            BYTE* m = *(BYTE**)(ent + 0x20);
            const float* p = m ? (const float*)(m + 0x30) : (const float*)(ent + 0x10);
            float dx = p[0] - centre[0], dy = p[1] - centre[1], dz = p[2] - centre[2];
            cand[n].d2 = dx * dx + dy * dy + dz * dz; cand[n].ent = ent; n++;
        }
        // farthest first; n is at most a few hundred, so a selection pass per deletion is fine
        int deleted = 0;
        for (int k = 0; k < want && n > 0; k++) {
            while (n > 0) {
                int best = 0;
                for (int i = 1; i < n; i++) if (cand[i].d2 > cand[best].d2) best = i;
                BYTE* ent = cand[best].ent;
                cand[best] = cand[--n];
                if (EntityOnScreen(ent)) { g_pfSpared++; continue; }
                ((void (__cdecl*)(BYTE*, int))(g_base + kRemovePedFnRva))(ent, 1);
                deleted++; g_pfDeleted++;
                break;
            }
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        Log("pool cull: exception, this frame skipped");
    }
}

static bool InstallPoolFull(BYTE* base)
{
    BYTE* p = base + kPoolFullRva;
    if (memcmp(p, kPoolFullSig, sizeof kPoolFullSig) != 0 || *(DWORD*)(p + sizeof kPoolFullSig) != (DWORD)base + kCookieRva) {
        Log("pool cull: 0x%X does not match (%02x %02x %02x %02x %02x %02x %02x %08X) - not replaced", kPoolFullRva, p[0], p[1], p[2], p[3], p[4], p[5], p[6], *(DWORD*)(p + 7));
        return false;
    }
    DWORD old;
    if (!VirtualProtect(p, 5, PAGE_EXECUTE_READWRITE, &old)) { Log("pool cull: VirtualProtect failed %lu", GetLastError()); return false; }
    p[0] = 0xE9; *(DWORD*)(p + 1) = (DWORD)&PoolFullCull - (DWORD)(p + 5);
    VirtualProtect(p, 5, old, &old);
    FlushInstructionCache(GetCurrentProcess(), p, 5);
    Log("pool cull: 0x%X replaced; off-camera far peds go first, on-camera ones are never taken", kPoolFullRva);
    return true;
}

static bool PatchDisp(BYTE* base, DWORD siteRva, DWORD constRva, float* target, const char* name, BYTE modrm = 0x05)
{
    BYTE* p = base + siteRva;
    if (p[0] != 0x0f || p[1] != 0x2f || p[2] != modrm) { Log("%s: opcode mismatch at RVA %X (%02x %02x %02x)", name, siteRva, p[0], p[1], p[2]); return false; }
    DWORD disp = *(DWORD*)(p + 3);
    DWORD expect = (DWORD)base + constRva;
    if (disp != expect) { Log("%s: displacement %08X != expected %08X (base %p)", name, disp, expect, base); return false; }
    DWORD old;
    if (!VirtualProtect(p + 3, 4, PAGE_EXECUTE_READWRITE, &old)) { Log("%s: VirtualProtect failed %lu", name, GetLastError()); return false; }
    *(DWORD*)(p + 3) = (DWORD)target;
    VirtualProtect(p + 3, 4, old, &old);
    FlushInstructionCache(GetCurrentProcess(), p, 8);
    Log("%s: RVA %X now reads %p (%.0f m^2 = %.1f m)", name, siteRva, target, *target, sqrtf(*target));
    return true;
}

// ---- removal trace ----------------------------------------------------------------------------
// [popctl] TraceRemovals=1 hooks CPopulation::RemovePed (RVA 0x73BCD0), the one function every
// population cull goes through (49 call sites), and writes a line per deleted ped to popctl_trace.log:
// which caller deleted it, how far from the player it stood, whether the camera could see it, the
// per-ped "seen" flag and cull scale the engine consulted, and how full the two population pools
// were. This is a measurement tool; it costs nothing when off.
static const DWORD kRemovePedRva  = 0x73BCD0;   // void __cdecl RemovePed(CEntity*, bool)
static const BYTE  kRemovePedSig[] = { 0x80,0x7c,0x24,0x08,0x00, 0x56, 0x8b,0x74,0x24,0x08 };   // cmp byte [esp+8],0; push esi; mov esi,[esp+8]
static const DWORD kPedPoolRva    = 0x14B6F1C;  // CPool* : 120 x 0xEF0 (CPed)
static const DWORD kSecondPoolRva = 0x14B6F10;  // CPool* : 150 x 0x3B0 (second population class)
static const DWORD kFindPlayerRva = 0x53F050;   // CPed* __cdecl FindPlayerPed()
static const DWORD kOnScreenRva   = 0x631B10;   // bool __thiscall IsVisibleToCamera(bool)
static const DWORD kSeenFlagRva   = 0x5E7490;   // bool __thiscall: byte +0x142 of the vtable+0xD4 object
static const DWORD kCullScaleRva  = 0x5E88E0;   // float __thiscall: float +0x144 of the same object
static const DWORD kFrameRva      = 0xD73604;   // frame counter
static const DWORD kTimeRva       = 0xD735B4;   // game time, ms

static bool  g_trace;
static char  g_traceLog[MAX_PATH];
static BYTE* g_removeRet;
static DWORD g_traceLines;

static void TraceLine(const char* fmt, ...)
{
    if (g_traceLines++ > 200000) return;
    FILE* f = fopen(g_traceLog, "a"); if (!f) return;
    va_list ap; va_start(ap, fmt); vfprintf(f, fmt, ap); va_end(ap);
    fputc('\n', f); fclose(f);
}

struct PoolHdr { BYTE* storage; BYTE* flags; int size; int elem; int lastFree; int used; };
static PoolHdr* PoolAt(DWORD rva) { PoolHdr** pp = (PoolHdr**)(g_base + rva); return pp ? *pp : nullptr; }
static int PoolIndex(PoolHdr* p, BYTE* ent)
{
    if (!p || !p->storage || p->elem <= 0) return -1;
    if (ent < p->storage || ent >= p->storage + (size_t)p->size * p->elem) return -1;
    return (int)((ent - p->storage) / p->elem);
}
static const float* EntPos(BYTE* ent)
{
    BYTE* m = *(BYTE**)(ent + 0x20);
    return m ? (const float*)(m + 0x30) : (const float*)(ent + 0x10);
}
// Keyed on the return address (call site + 5).
static const char* CallerName(DWORD rva)
{
    switch (rva) {
    case 0x73B072: return "hidden";       // 0x73AF50: CPeds off camera past 80 m (seen flag) / 15 m, immediate. popctl's original patch
    case 0x73B17B: return "band";         // 0x73B090: CPeds past 115 m any, 70-115 m off camera and never seen, after a 2.5-3.5 s timer
    case 0x7385FE: return "poolfull";     // 0x738430: far pool under 12 free slots: farthest first, up to 20 per frame, no visibility test
    case 0x73840D + 5: return "modeltimer";   // 0x738360: model-flagged CPeds whose timer expired
    case 0x73833F: return "flagged";      // 0x7382A0: far peds with byte +0x3A2 set
    case 0x738724: return "farhidden";    // 0x738620: far peds off camera past 15 m, immediate
    case 0x738839: return "farband";      // 0x738740: far peds, same band test as "band"
    case 0x73815F: case 0x738176: case 0x7381E7: return "cap15";   // 0x737EC0: class cap 15 (7 online)
    case 0x73BC82: case 0x73BCBF: return "removeall"; // 0x73BC40: everything, e.g. on a teleport
    case 0x73C760: return "toPed";        // 0x73C640: far ped replaced by a full CPed as you approach (~30 m)
    case 0x73C940: return "toFar";        // 0x73C8C0: CPed replaced by a far ped as you leave (~35 m)
    case 0x5409A5: return "script";       // 0x540980: generic DeleteEntity, scripts and natives
    case 0x883969: case 0x883AB9: return "list";
    default: return "other";
    }
}

// The three engine queries are __thiscall and one returns on the x87 stack, so each is wrapped in
// its own out-of-line function: the compiler then treats the call as a real call and keeps nothing
// live in the registers the engine clobbers. (An earlier inline version printed negated distances.)
static __declspec(noinline) int CallSeenFlag(BYTE* self)
{
    BYTE r = 0; DWORD fn = (DWORD)(g_base + kSeenFlagRva);
    __asm {
        mov ecx, self
        call fn
        mov r, al
    }
    return r;
}
static __declspec(noinline) float CallCullScale(BYTE* self)
{
    float sc = 0.0f; DWORD fn = (DWORD)(g_base + kCullScaleRva);
    __asm {
        mov ecx, self
        call fn
        fstp sc
    }
    return sc;
}
static __declspec(noinline) int CallOnScreen(BYTE* self)
{
    BYTE r = 0; DWORD fn = (DWORD)(g_base + kOnScreenRva);
    __asm {
        mov ecx, self
        push 1
        call fn
        mov r, al
    }
    return r;
}

static void __cdecl TraceRemove(DWORD* frame, DWORD retAddr, BYTE* ent, int flag)
{
    __try {
        DWORD rva = retAddr - (DWORD)g_base;
        // two more return addresses up the stack, for callers like DeleteEntity that are themselves generic
        DWORD up1 = frame[4] - (DWORD)g_base, up2 = frame[5] - (DWORD)g_base;
        if (up1 > 0x1BE6400) up1 = 0; if (up2 > 0x1BE6400) up2 = 0;
        BYTE* intel = *(BYTE**)(ent + 0x6C);
        int mission = intel ? intel[0xE] : -1;
        bool ours = g_self && retAddr >= (DWORD)g_self && retAddr < (DWORD)g_self + 0x40000;
        PoolHdr* P = PoolAt(kPedPoolRva); PoolHdr* Q = PoolAt(kSecondPoolRva);
        int ip = PoolIndex(P, ent), iq = PoolIndex(Q, ent);
        const float* pos = EntPos(ent);
        int seen = -1, vis = -1; float scale = -1.0f;
        __try {
            seen = CallSeenFlag(ent);
            scale = CallCullScale(ent);
            vis = CallOnScreen(ent);
        } __except (EXCEPTION_EXECUTE_HANDLER) { }
        volatile float dist = -1.0f;
        BYTE* player = ((BYTE* (__cdecl*)())(g_base + kFindPlayerRva))();
        if (player) {
            const float* pp = EntPos(player);
            float dx = pos[0] - pp[0], dy = pos[1] - pp[1], dz = pos[2] - pp[2];
            dist = sqrtf(dx * dx + dy * dy + dz * dz);
        }
        TraceLine("t=%u f=%u %-10s caller=%X up=%X/%X m=%d pool=%c%d type=%d model=%d flag=%d dist=%.1f seen=%d vis=%d scale=%.2f used=%d/%d q=%d/%d pos=%.1f,%.1f,%.1f",
            *(DWORD*)(g_base + kTimeRva), *(DWORD*)(g_base + kFrameRva), ours ? "poolfull*" : CallerName(rva), rva, up1, up2, mission,
            ip >= 0 ? 'P' : (iq >= 0 ? 'Q' : '?'), ip >= 0 ? ip : iq,
            (*(DWORD*)(ent + 0x28) >> 6) & 0xF, *(short*)(ent + 0x2E), flag, dist, seen, vis, scale,
            P ? P->used : -1, P ? P->size : -1, Q ? Q->used : -1, Q ? Q->size : -1, pos[0], pos[1], pos[2]);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        TraceLine("trace: exception while logging a removal from %X", retAddr - (DWORD)g_base);
    }
}

static __declspec(naked) void RemoveHook()
{
    __asm {
        pushad
        pushfd
        push dword ptr [esp + 0x2c]     // flag
        push dword ptr [esp + 0x2c]     // entity
        push dword ptr [esp + 0x2c]     // return address = the caller
        lea eax, [esp + 0x30]           // the original frame: [0] return address, [1] entity, [2] flag
        push eax
        call TraceRemove
        add esp, 16
        popfd
        popad
        cmp byte ptr [esp + 8], 0       // the five bytes the jmp replaced
        jmp dword ptr [g_removeRet]
    }
}

static void TraceStatus()
{
    __try {
        PoolHdr* P = PoolAt(kPedPoolRva); PoolHdr* Q = PoolAt(kSecondPoolRva);
        BYTE* player = ((BYTE* (__cdecl*)())(g_base + kFindPlayerRva))();
        const float* pp = player ? EntPos(player) : nullptr;
        TraceLine("status t=%u f=%u used=%d/%d q=%d/%d player=%.1f,%.1f,%.1f cull(calls=%u deleted=%u spared=%u)",
            *(DWORD*)(g_base + kTimeRva), *(DWORD*)(g_base + kFrameRva),
            P ? P->used : -1, P ? P->size : -1, Q ? Q->used : -1, Q ? Q->size : -1,
            pp ? pp[0] : 0.0f, pp ? pp[1] : 0.0f, pp ? pp[2] : 0.0f, g_pfCalls, g_pfDeleted, g_pfSpared);
    } __except (EXCEPTION_EXECUTE_HANDLER) { }
}

static bool InstallTrace(BYTE* base)
{
    BYTE* p = base + kRemovePedRva;
    if (memcmp(p, kRemovePedSig, sizeof kRemovePedSig) != 0) {
        Log("trace: RemovePed at RVA %X does not match (%02x %02x %02x %02x %02x) - not hooked", kRemovePedRva, p[0], p[1], p[2], p[3], p[4]);
        return false;
    }
    g_removeRet = p + 5;
    DWORD old;
    if (!VirtualProtect(p, 5, PAGE_EXECUTE_READWRITE, &old)) { Log("trace: VirtualProtect failed %lu", GetLastError()); return false; }
    p[0] = 0xE9; *(DWORD*)(p + 1) = (DWORD)&RemoveHook - (DWORD)(p + 5);
    VirtualProtect(p, 5, old, &old);
    FlushInstructionCache(GetCurrentProcess(), p, 5);
    Log("trace: RemovePed hooked, writing %s", g_traceLog);
    return true;
}

// First fatal exception in the process: EIP as a GTAIV.exe RVA, the faulting access, registers, and
// every stack dword that lands inside GTAIV.exe or this DLL. Then EXCEPTION_CONTINUE_SEARCH, so the
// game's own handler still runs. This only ever reads and logs; it never swallows a crash.
static LONG g_excLogged = 0;
static LONG CALLBACK ExcLogger(EXCEPTION_POINTERS* ep)
{
    const DWORD code = ep->ExceptionRecord->ExceptionCode;
    if (code != EXCEPTION_ACCESS_VIOLATION && code != EXCEPTION_ILLEGAL_INSTRUCTION && code != EXCEPTION_STACK_OVERFLOW
        && code != EXCEPTION_INT_DIVIDE_BY_ZERO && code != EXCEPTION_PRIV_INSTRUCTION) return EXCEPTION_CONTINUE_SEARCH;
    if (InterlockedIncrement(&g_excLogged) > 6) return EXCEPTION_CONTINUE_SEARCH;
    BYTE* base = (BYTE*)GetModuleHandleA(NULL);
    DWORD exeSize = 0x1BE6400;   // 1.2.0.59 SizeOfImage
    CONTEXT* c = ep->ContextRecord;
    DWORD eip = c->Eip;
    HMODULE owner = nullptr; char modName[MAX_PATH] = "?";
    if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT, (LPCSTR)eip, &owner) && owner) {
        GetModuleFileNameA(owner, modName, sizeof modName);
        const char* slash = strrchr(modName, '\\'); if (slash) memmove(modName, slash + 1, strlen(slash));
    }
    Log("EXCEPTION %08X at %08X (%s+0x%X) tid %lu", code, eip, modName, eip - (DWORD)(owner ? owner : (HMODULE)base), GetCurrentThreadId());
    if (code == EXCEPTION_ACCESS_VIOLATION && ep->ExceptionRecord->NumberParameters >= 2)
        Log("  %s at %08X", ep->ExceptionRecord->ExceptionInformation[0] ? "write" : "read", (DWORD)ep->ExceptionRecord->ExceptionInformation[1]);
    Log("  eax %08X ebx %08X ecx %08X edx %08X esi %08X edi %08X ebp %08X esp %08X", c->Eax, c->Ebx, c->Ecx, c->Edx, c->Esi, c->Edi, c->Ebp, c->Esp);
    DWORD* sp = (DWORD*)(c->Esp & ~3u);
    int shown = 0;
    for (int i = 0; i < 512 && shown < 24; i++) {
        MEMORY_BASIC_INFORMATION mbi;
        if (!VirtualQuery(sp + i, &mbi, sizeof mbi) || !(mbi.State & MEM_COMMIT) || (mbi.Protect & (PAGE_NOACCESS | PAGE_GUARD))) break;
        DWORD v = sp[i];
        if (v >= (DWORD)base && v < (DWORD)base + exeSize) { Log("  stack[%3d] %08X  GTAIV.exe+0x%X", i, v, v - (DWORD)base); shown++; }
        else if (g_self && v >= (DWORD)g_self && v < (DWORD)g_self + 0x40000) { Log("  stack[%3d] %08X  popctl+0x%X", i, v, v - (DWORD)g_self); shown++; }
    }
    return EXCEPTION_CONTINUE_SEARCH;
}

static DWORD WINAPI Worker(LPVOID)
{
    BYTE* base = (BYTE*)GetModuleHandleA(NULL);
    Log("base %p; waiting for decrypted .text at RVA %X", base, kSigRva);
    for (int i = 0; i < 1200; i++) {   // up to 2 minutes
        MEMORY_BASIC_INFORMATION mbi;
        if (VirtualQuery(base + kSigRva, &mbi, sizeof mbi) && (mbi.State & MEM_COMMIT) && !(mbi.Protect & PAGE_NOACCESS) && !(mbi.Protect & PAGE_GUARD)) {
            if (memcmp(base + kSigRva, kSig, sizeof kSig) == 0) {
                Log("signature present after %d polls", i);
                g_far = g_cfgFar * g_cfgFar; g_near = g_cfgNear * g_cfgNear;
                bool a = PatchDisp(base, kSiteFar, kConstFarRva, &g_far, "hidden");
                bool b = PatchDisp(base, kSiteNear, kConstNearRva, &g_near, "near");
                bool c = PatchDisp(base, kFarPoolNearSiteRva, kConstNearRva, &g_near, "far pool near", 0x15);
                bool d = PokeFloat(base, kVisibleKeepRva, 115.0f, g_cfgVisible, "visible");
                bool e = PokeFloat(base, kHiddenBandRva, 70.0f, g_cfgFar, "hidden band");
                Log(a && b && c && d && e ? "patched: visible %.0f m, hidden %.0f m, near %.0f m" : "PATCH INCOMPLETE - see above", g_cfgVisible, g_cfgFar, g_cfgNear);
                if (g_cfgSpawns != 8) PatchSpawns(base);
                InstallPoolFull(base);
                bool tracing = g_trace && InstallTrace(base);
                // some CVehiclePopulation statics are only set during game init (VehAttemptScale reads
                // 1.0 until then), so keep offering the pokes for a minute; each one applies once. The
                // pools are constructed during init too: report their live sizes once they exist.
                // With the trace on, stay alive and write a pool/player status line every 2 s.
                bool pools = false;
                for (int j = 0; j < 600 || tracing || !pools; j++) {
                    if (j < 600) ApplyPokes(base);
                    if (!pools && *(BYTE**)(base + kFarPoolPtrRva) && *(BYTE**)(base + kPedPoolPtrRva)) { pools = true; ReportPools(base); }
                    if (tracing && j % 20 == 0) TraceStatus();
                    if (j > 6000 && !tracing) break;   // ten minutes without pools: give up quietly
                    Sleep(100);
                }
                return 0;
            }
        }
        Sleep(100);
    }
    Log("signature never appeared; nothing patched");
    return 0;
}

BOOL APIENTRY DllMain(HMODULE mod, DWORD reason, LPVOID)
{
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(mod);
        g_self = mod;
        AddVectoredExceptionHandler(1, ExcLogger);
        char path[MAX_PATH]; GetModuleFileNameA(mod, path, MAX_PATH);
        char* dot = strrchr(path, '.'); if (dot) *dot = 0;
        sprintf(g_log, "%s.log", path); sprintf(g_ini, "%s.ini", path);
        char buf[32];
        g_cfgFarPool = GetPrivateProfileIntA("popctl", "FarPedPool", 150, g_ini);
        if (g_cfgFarPool < kFarPoolStock) g_cfgFarPool = kFarPoolStock; if (g_cfgFarPool > 600) g_cfgFarPool = 600;
        g_cfgVehPool = GetPrivateProfileIntA("popctl", "VehiclePool", 140, g_ini);
        if (g_cfgVehPool < kVehPoolStock) g_cfgVehPool = kVehPoolStock; if (g_cfgVehPool > 300) g_cfgVehPool = 300;
        GetPrivateProfileStringA("popctl", "VisibleKeepMetres", "130", buf, sizeof buf, g_ini); g_cfgVisible = (float)atof(buf);
        // FarKeepMetres is the 0.1 name for HiddenKeepMetres; still honoured if the new key is absent.
        GetPrivateProfileStringA("popctl", "FarKeepMetres", "130", buf, sizeof buf, g_ini); g_cfgFar = (float)atof(buf);
        GetPrivateProfileStringA("popctl", "HiddenKeepMetres", buf, buf, sizeof buf, g_ini); g_cfgFar = (float)atof(buf);
        GetPrivateProfileStringA("popctl", "NearKeepMetres", "130", buf, sizeof buf, g_ini); g_cfgNear = (float)atof(buf);
        if (g_cfgVisible < 50.0f) g_cfgVisible = 50.0f; if (g_cfgVisible > 400.0f) g_cfgVisible = 400.0f;
        if (g_cfgFar < 20.0f) g_cfgFar = 20.0f; if (g_cfgFar > g_cfgVisible) g_cfgFar = g_cfgVisible;
        if (g_cfgNear < 5.0f) g_cfgNear = 5.0f;  if (g_cfgNear > g_cfgFar) g_cfgNear = g_cfgFar;
        g_cfgSpawns = GetPrivateProfileIntA("popctl", "SpawnsPerFrame", 8, g_ini);
        if (g_cfgSpawns < 1) g_cfgSpawns = 1; if (g_cfgSpawns > 64) g_cfgSpawns = 64;
        LoadPokes();
        g_base = (BYTE*)GetModuleHandleA(NULL);
        g_trace = GetPrivateProfileIntA("popctl", "TraceRemovals", 0, g_ini) != 0;
        if (g_trace) { sprintf(g_traceLog, "%s_trace.log", path); FILE* t = fopen(g_traceLog, "w"); if (t) fclose(t); }
        Log("popctl loaded: FarPedPool=%d VehiclePool=%d VisibleKeepMetres=%.0f HiddenKeepMetres=%.0f NearKeepMetres=%.0f SpawnsPerFrame=%d (stock 150 / 140 / 115 / 80 / 15 / 8)%s",
            g_cfgFarPool, g_cfgVehPool, g_cfgVisible, g_cfgFar, g_cfgNear, g_cfgSpawns, g_trace ? " trace on" : "");
        PatchPools(g_base);   // before the game constructs its pools
        HANDLE t = CreateThread(NULL, 0, Worker, NULL, 0, NULL);
        if (t) CloseHandle(t);
    }
    return TRUE;
}
