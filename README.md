# popctl

**Population control for GTA IV: The Complete Edition.** A research release: locating what actually
removes ambient pedestrians and traffic, and moving it.

One plugin, one job. Engine audio slots are a separate limit with a separate fix,
[revd](https://github.com/gutbash/revd). The two are independent.

## What you will see

Denser crowds that reach further down the street, and that stop vanishing in groups while you watch.
The stock game holds at most 150 far pedestrians and cuts the visible crowd off wherever the 138th
farthest one stands, a median 74 m on a busy block, in batches, whether or not you are looking. With
popctl 0.2 there are 300, the batch cull never takes a pedestrian the camera can see, and the crowd
is kept and spawned out to 130 m.

What you will not see:

- **More people inside about 30 m.** Those are full peds from a separate pool of 120 that popctl
  does not grow.
- **A full street behind you when you turn round.** The far pool is finite. When it is full the
  farthest off-camera pedestrians go first, so the crowd behind you thins with distance.
- **Any change in subway stations or other interiors.** They are populated by scenario points and the
  popcycle interior column, neither of which popctl touches.
- **Textured pedestrians past the texture streaming range.** Stock deleted them before you could see
  it; popctl keeps them, and past roughly 100 m they draw grey. `VisibleKeepMetres` is the lever.
- **Denser traffic.** The vehicle pool cannot be grown the same way; see Limitations.

## Abstract

Ambient pedestrians in GTA IV vanish at a fixed distance in front of the player, in groups, and the
settings modders reach for do not change it. popctl 0.1 located a distance cull in the population
manager and moved it, and shipped with the claim that this was the mechanism. It was not. Hooking the
one function every pedestrian removal passes through and logging each deletion's caller, distance and
visibility showed that the cull 0.1 patched never deletes a pedestrian the camera can see. The visible
cut-off comes from a second, lightweight pedestrian pool of 150 slots that stock GTA IV runs full: when
it has fewer than twelve free slots the manager deletes the farthest entries, up to twenty per frame,
with no visibility test. On one 180 s route this path produced 4,426 of 8,129 deletions, 2,847 of them
on camera. popctl 0.2 replaces that cull with one of the same budget that only takes off-camera
pedestrians, doubles the pool together with the twelve engine pools sized to it, and moves the shared
keep and spawn distances to 130 m. The trace that found all of this ships in the plugin as an option.

## Problem

The community-standard levers for crowd density are `popcycle.dat`, the density multiplier natives and
the vehicle density command-line flags. Tested on 2026-09-06 against a pedestrian census, none of them
moved the count past roughly 60 m. popctl 0.1 then moved the two distance constants it had found in
the removal loop at `0x73AF50`, from 80 m and 15 m to 120 m and 45 m. Users reported no visible change,
and pedestrians still disappeared in front of the player in groups of one to eight. Both reports were
correct.

## Method

Every population cull ends in one function, `RemovePed` at RVA `0x73BCD0`, which has 49 call sites.
popctl 0.2 can hook it (`TraceRemovals = 1`) and write a line per deletion: the return address and
two more above it, the pool the entity came from, its distance from the player, whether the camera
could see it, the per-ped flags the engine consulted, and how full both pools were. Three hands-free
runs of the same 180 s camera route through northern Algonquin were traced with the stock game,
popctl 0.1's shipped values and popctl 0.2's, plus several hours of play on Star Junction.

The disassembly then explained each caller. Ambient pedestrians beyond roughly 30 m are not `CPed`
objects. They are 944-byte dummy peds (entity type 6, pool `0x14B6F10`, 150 slots) converted to a full
`CPed` (pool `0x14B6F1C`, 120 slots) as the player approaches and back as they leave. The population
code walks both pools with parallel functions:

| Path | Pool | Rule |
|---|---|---|
| `0x738430` pool nearly full | far | under 12 free slots: delete the farthest, up to 20 per frame, no visibility test |
| `0x737240` band cull | both | past 115 m deleted even on camera (×1.5 for peds flagged seen); 70–115 m deleted if off camera and never flagged; 2.5–3.5 s grace timer |
| `0x73AF50` off-camera cull | full | past 80 m if flagged seen, else 15 m; immediate. **All popctl 0.1 patched** |
| `0x738620` off-camera cull | far | past 15 m; immediate |
| `0x73C640` / `0x73C8C0` | both | conversion between the pools; the ped is replaced in place |

Every one of them skips a ped whose mission flag is set, so scripts that hold peds are unaffected.

Growing the far pool is four immediates in its constructor at `0x1C41E0`. Doing only that crashed
within a minute, twice, and each dump named the next dependency: every ped also owns a record from a
pool sized exactly 120 + 150 (`0x1C3F70`), then an animation blender from a named pool of 300. The
game does not check either allocation for null. Enumerating the executable's 46 named pools and two
template constructors gave the full set: three pools at exactly 300 (`CAnimBlender`, `CDummyTask`,
`Event`) and six animation pools at multiples of 300. popctl scales all of them by the same ratio,
verifies every immediate against its stock value first, and writes none of them if any one fails.
The live pool headers are read back after the game constructs them and written to `popctl.log`.

## Findings

Removals in 180 s on the same route, from `data/trace_*.log`:

| | stock game | popctl 0.1 | popctl 0.2 |
|---|---|---|---|
| Far pool size | 150 | 150 | 300 |
| Far pool fill, median / peak | 135 / 148 | 135 / 150 | 288 / 300 |
| Deletions, all paths | 8,129 | 9,485 | 11,031 |
| Deleted for "pool nearly full" | 4,426 | 6,192 | 7,503 |
| of those, on camera | 2,847 at median 74 m | 4,094 at median 74 m | 0 |
| Deleted by the off-camera cull 0.1 patched | 21 | 25 | 0 |
| Average frame rate | 50.1 fps | 53.2 fps | 50.3 fps |

- **The visible cut-off is pool pressure, not a distance constant.** Stock GTA IV keeps its far-ped
  pool within twelve slots of full on a busy street, so the crowd ends wherever the 138th-farthest
  pedestrian stands. That is why it looks like a fixed radius and why no distance setting moved it.
- **popctl 0.1's patch was real but invisible.** The loop at `0x73AF50` skips any pedestrian the
  camera can see. Raising its distances changed what survived behind the player and nothing else. On
  the 0.1 run it accounted for 25 deletions out of 9,485. The Nexus report that "nothing changed" was
  accurate.
- **The spawner fills whatever it is given.** At 150, 300 and 450 slots the far pool sat within
  twelve of full for the whole session. Capacity, not spawn rate, sets the density; 0.1's doubled
  spawn rate only churned the pool faster and fired the batch cull more often.
- **450 far peds broke physics on the test machine.** With the pool at 438 of 450, peds and the
  player jittered vertically and fell through the map, which is what a starved frame budget does to
  the collision step. 300 ran clean. The setting is exposed; the default is the tested value.
- **Conversions are not despawns.** The two largest remaining callers replace a far ped with a full
  ped at about 30 m and back again. They look like nothing because the replacement stands where the
  original did.
- **Distance settings above the spawn band do nothing you can see.** With the batch cull no longer
  taking visible peds, the crowd's front edge is wherever the spawner stops placing them, 105 m in
  stock. `VisibleKeepMetres` at 130 and 160 looked identical until the spawn band moved with it.
- Frame rate on the route was within run-to-run noise across the three configurations. One route on
  one machine; not a performance characterisation.

## Figures

Generated by [`docs/make_figures.py`](docs/make_figures.py) from the addresses, the shipped config and
the trace logs in `data/`. Nothing in them is modelled.

| | |
|---|---|
| [Where a pedestrian is deleted](docs/figures/fig1_mechanism.png) | Both pools, every cull path, where 0.1 and 0.2 intervene |
| [Why not simply change the number?](docs/figures/fig2_constant_pool.png) | The shared constant pool and its other readers |
| [Cull distances, drawn to scale](docs/figures/fig3_radius.png) | Stock against the shipped configuration |
| [What deleted the pedestrians](docs/figures/fig4_trace.png) | The three traces, by path, with on-camera counts |
| [Every value popctl changes](docs/figures/fig5_settings.png) | Address, stock, shipped, purpose |

## Explainer

A short animated walkthrough of the problem, the mechanism and the fix:
[`docs/video/popctl_explainer.mp4`](docs/video/popctl_explainer.mp4). Source, in Manim, is
[`docs/video/explainer.py`](docs/video/explainer.py).

## Installation

1. Have an ASI loader present. Ultimate ASI Loader as `dinput8.dll` is the usual one, and if you run
   FusionFix you already have it.
2. Put `popctl.asi` and `popctl.ini` in your `GTAIV` folder, next to `GTAIV.exe`.
3. Launch. `popctl.log` appears next to the plugin and records every patch attempt and its outcome,
   including the live size of each pool once the game has created them.

To uninstall, delete both files. Nothing is written to disk by the plugin and no game file is modified.

Upgrading from 0.1: replace both files. The old `FarKeepMetres` key is still read as
`HiddenKeepMetres` if the new key is absent; `SpawnsPerFrame` should go back to 8.

## Configuration

`popctl.ini` is commented in full. `FarPedPool` is the setting that matters and 300 is the tested
value. `VisibleKeepMetres`, `HiddenKeepMetres` and `NearKeepMetres` ship equal at 130 so that pool
pressure, not a fixed radius, decides what survives behind you; lower the visible one if the grey
far-ped models or the pop-in bother you more than crowd depth. The `[Pokes]` section takes raw
`RVA,type,stock,new` entries for the vehicle statics and the ped spawn band, and a value is written
only while the address still reads its stock value.

`TraceRemovals = 1` writes `popctl_trace.log`, one line per deleted pedestrian. It is how everything
above was measured and it is the first thing to turn on if you think popctl is not doing what it says.

## Limitations

These are the boundaries of what was tested. Nothing outside them should be assumed to work.

- **Complete Edition 1.2.0.59 only.** Every address is a hardcoded RVA for that exact build. On any
  other version the checks fail, nothing is patched, and the log says so.
- **The vehicle pool cannot be grown this way.** Raising it from 140 to 200 with the car budget at
  150 crashed after three minutes with the CPU jumping into a data address
  (`data/MiniDump_20260915_vehpool200.dmp`), the signature of a 140-entry table indexed by vehicle
  slot. It was not pursued. Traffic is bounded by the 110-car budget and the 140-slot pool as before.
- **The full-ped pool is not grown.** It peaked at 111 of 120 during play at 300 far peds. Its own
  dependents were not enumerated.
- **One machine, one mod stack.** The route numbers are from a camera flythrough with the player
  teleported along it; the density and physics observations are from play on Star Junction with
  FusionFix loaded. Frame rate was recorded on the route, not characterised.
- **The "seen" flag is inferred.** The per-ped byte at `+0x142` behaves like a has-been-seen flag
  and is treated as one.
- **Texture streaming is out of scope.** Far peds past roughly 100 m draw untextured. That is the
  streamer's range, not the population manager's.

## Reproducibility

Turn on `TraceRemovals`, play, and read `popctl_trace.log`; `docs/make_figures.py` will chart any
`data/trace_*.log`. Anyone reproducing the numbers above should report game build, the route or play
pattern, and the pool sizes from `popctl.log`. Open questions: the frame-time cost curve against
`FarPedPool`, the full-ped pool's dependents, which table the vehicle pool overran, and the flag
semantics.

## Building

Windows, Visual Studio 2022 with the x86 toolchain. Single translation unit, no dependencies beyond
the Win32 SDK. Every commit is built by public GitHub Actions.

```
.\build.ps1            # produces popctl.asi
.\build.ps1 -Deploy    # and copies it into the game folder
```

## License

MIT. See [LICENSE](LICENSE).
