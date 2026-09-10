// popctl.asi - population control for GTA IV: The Complete Edition (1.2.0.59).
//
// Three things, all of them population:
//
//   1. Ambient ped keep radius. CPopulation's removal loop (RVA 0x73AF50, called from the population
//      Process at 0x73B540) walks every ped, takes the squared distance to the player and compares it
//      with a const-pool float: 6400 (80 m) on one branch, 225 (15 m) on the other (a per-ped flag read
//      through vtable+0xD4, then byte +0x142 - on-screen or similar). Anything beyond is deleted. That,
//      not popcycle.dat and not the density multiplier natives, is why crowds vanish just past ~60 m.
//
//      Both constants live in the shared const pool (the 60.0 next to them has 119 users), so the
//      constant itself cannot change. This patches the two 4-byte displacements of the
//      `comiss xmm0, [addr]` at RVA 0x73B04B and 0x73B054 to point at floats inside this DLL.
//
//   2. Ambient spawns per frame. CPopulation::Process reads the per-frame spawn cap from the data
//      global at RVA 0xC4594C (stock 8) and makes at most that many attempts from the <= 16 candidate
//      nodes it gathered. Values above 16 do nothing, because 16 is all it gathers.
//
//   3. Vehicle population statics ([Pokes]). The CVehiclePopulation block at RVA 0xC3FF60 holds the
//      traffic generation band, the removal distances and the ambient car budget.
//
// Nothing on disk is modified; every patch is made in memory, at runtime. The Complete Edition's .text
// is encrypted at load, so the patch waits (polling) until the expected instruction bytes are present,
// verifies each displacement against the live base, and only then writes. Any site that does not read
// its expected stock value is left alone and logged, so a different game build is a no-op rather than a
// crash. Log: popctl.log next to the .asi.
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

static bool PatchDisp(BYTE* base, DWORD siteRva, DWORD constRva, float* target, const char* name)
{
    BYTE* p = base + siteRva;
    if (p[0] != 0x0f || p[1] != 0x2f || p[2] != 0x05) { Log("%s: opcode mismatch at RVA %X (%02x %02x %02x)", name, siteRva, p[0], p[1], p[2]); return false; }
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

// First fatal exception in the process: EIP as a GTAIV.exe RVA, the faulting access, registers, and
// every stack dword that lands inside GTAIV.exe or this DLL. Then EXCEPTION_CONTINUE_SEARCH, so the
// game's own handler still runs. This only ever reads and logs; it never swallows a crash.
static LONG g_excLogged = 0;
static HMODULE g_self = nullptr;
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
                bool a = PatchDisp(base, kSiteFar, kConstFarRva, &g_far, "far");
                bool b = PatchDisp(base, kSiteNear, kConstNearRva, &g_near, "near");
                Log(a && b ? "patched: far %.0f m, near %.0f m" : "PATCH INCOMPLETE - game left stock", g_cfgFar, g_cfgNear);
                if (g_cfgSpawns != 8) PatchSpawns(base);
                // some CVehiclePopulation statics are only set during game init (VehAttemptScale reads
                // 1.0 until then), so keep offering the pokes for a minute; each one applies once.
                for (int j = 0; j < 600; j++) { ApplyPokes(base); Sleep(100); }
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
        GetPrivateProfileStringA("popctl", "FarKeepMetres", "80", buf, sizeof buf, g_ini);  g_cfgFar = (float)atof(buf);
        GetPrivateProfileStringA("popctl", "NearKeepMetres", "15", buf, sizeof buf, g_ini); g_cfgNear = (float)atof(buf);
        if (g_cfgFar < 20.0f) g_cfgFar = 20.0f; if (g_cfgFar > 400.0f) g_cfgFar = 400.0f;
        if (g_cfgNear < 5.0f) g_cfgNear = 5.0f;  if (g_cfgNear > g_cfgFar) g_cfgNear = g_cfgFar;
        g_cfgSpawns = GetPrivateProfileIntA("popctl", "SpawnsPerFrame", 8, g_ini);
        if (g_cfgSpawns < 1) g_cfgSpawns = 1; if (g_cfgSpawns > 64) g_cfgSpawns = 64;
        LoadPokes();
        Log("popctl loaded: FarKeepMetres=%.0f NearKeepMetres=%.0f SpawnsPerFrame=%d (stock 80 / 15 / 8)", g_cfgFar, g_cfgNear, g_cfgSpawns);
        HANDLE t = CreateThread(NULL, 0, Worker, NULL, 0, NULL);
        if (t) CloseHandle(t);
    }
    return TRUE;
}
