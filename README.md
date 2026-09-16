# popctl

**Population control for GTA IV: The Complete Edition.** A research release: locating what actually
removes ambient pedestrians, and moving it.

One plugin, one job. Engine audio slots are a separate limit with a separate fix,
[revd](https://github.com/gutbash/revd). The two are independent.

## Abstract

Ambient pedestrians in GTA IV vanish in groups at what looks like a fixed distance in front of the
player, and no density setting changes it. The distance is not a constant. Pedestrians beyond roughly
30 m are lightweight dummy peds in a pool of 150 slots, and the population manager, whenever fewer
than twelve slots are free, deletes the farthest entries at up to twenty per frame with no visibility
test. On any busy street the pool is within twelve of full, so the crowd ends wherever the
138th-farthest pedestrian stands: a median 74 m on the test route, in batches, on camera. popctl 0.2
replaces that cull with one of the same budget that only takes pedestrians the camera cannot see,
grows the pool to 300 together with the twelve engine pools sized to it, and moves the shared keep and
spawn distances to 130 m. Every claim here comes from a hook on the one function all 49 removal paths
pass through, which ships in the plugin as an option.

## Problem

The community-standard levers for crowd density are `popcycle.dat`, the density multiplier natives and
the vehicle density command-line flags. Tested against a pedestrian census on 2026-09-06, none of them
moved the count past roughly 60 m.

popctl 0.1 then located a distance cull in the population manager at RVA `0x73AF50`, comparing squared
distance against 6400 (80 m) or 225 (15 m), and moved both. It shipped with the claim that this was the
mechanism. Users reported no visible change and that pedestrians still vanished in groups. Both reports
were correct: that loop skips every pedestrian the camera can see, so raising its distances changed
what survived behind the player and nothing else. In a three-minute run it accounted for 25 deletions
out of 9,485.

## Method

**Trace.** Every population cull ends in `RemovePed` at RVA `0x73BCD0`. popctl hooks it
(`TraceRemovals = 1`) and writes one line per deletion: the return address and two above it, the pool
the entity came from, its distance from the player, whether the camera could see it, the flags the
engine consulted, and the fill of both pools. Three hands-free runs of the same 180 s camera route
through northern Algonquin were traced (stock, 0.1, 0.2), plus several hours of play on Star Junction.
The logs are in [`data/`](data/).

**Mechanism.** The disassembly then explained each caller. Ambient pedestrians beyond about 30 m are
dummy peds (entity type 6, 944 bytes, pool `0x14B6F10`, 150 slots), swapped for a full `CPed` (pool
`0x14B6F1C`, 120 slots) as the player approaches and back as they leave. The population code walks
both pools with parallel functions:

| Path | Pool | Rule |
|---|---|---|
| `0x738430` pool nearly full | far | under 12 free slots: delete the farthest, up to 20 per frame, no visibility test |
| `0x737240` band cull | both | past 115 m deleted even on camera (×1.5 for peds flagged seen); 70–115 m deleted if off camera and never flagged; 2.5–3.5 s grace timer. Floats at `0xC45994`, `0xC45990` |
| `0x73AF50` / `0x738620` off-camera cull | full / far | past 80 m if flagged seen, else 15 m; immediate. **All popctl 0.1 patched** |
| `0x73C640` / `0x73C8C0` | both | conversion between the pools; the ped is replaced in place |

Every one of them skips a ped whose mission flag is set.

**Cull replacement.** `0x738430` is replaced by a function with the same contract and budget that walks
the pool, sorts by distance, and skips any candidate the camera can see. If every far ped is in view,
nothing is deleted and spawning pauses, which the spawner already handles: it checks free slots before
creating.

**Pool growth.** The far pool's size is four immediates in its constructor at `0x1C41E0`. Growing only
that crashed within a minute, twice, and each dump named the next dependency: a record pool sized
exactly 120 + 150 (`0x1C3F70`), then an animation blender from a named pool of 300. The game does not
null-check either. Enumerating the executable's 46 named pools and two template constructors gave the
full set: three pools at exactly 300 (`CAnimBlender`, `CDummyTask`, `Event`) and six animation pools at
multiples of 300. popctl scales all of them by (120 + far) / 270, verifies every immediate against its
stock value first, writes none if any one fails, and reads the live pool headers back after the game
constructs them.

**Distances.** The band floats are written directly. The off-camera constants are shared read-only
pool entries, so the `comiss` displacements at `0x73B04B`, `0x73B054` and `0x738700` are repointed at
floats inside the plugin. The spawner's far edge (`0xC45980`, stock 105) is moved to match.

## Findings

Deletions in 180 s on the same route, every one logged:

| | stock game | popctl 0.1 | popctl 0.2 |
|---|---|---|---|
| Far pool size | 150 | 150 | 300 |
| Far pool fill, median / peak | 135 / 148 | 135 / 150 | 288 / 300 |
| Deletions, all paths | 8,129 | 9,485 | 11,031 |
| Deleted for "pool nearly full" | 4,426 | 6,192 | 7,503 |
| of those, on camera | 2,847 at median 74 m | 4,094 at median 74 m | 0 |
| Deleted by the off-camera cull 0.1 patched | 21 | 25 | 0 |
| Average frame rate | 50.1 fps | 53.2 fps | 50.3 fps |

- **The visible cut-off is pool pressure, not a distance constant.** The far pool sat within twelve
  of full for the whole route in every configuration. That is why it looks like a fixed radius, why it
  happens in groups, and why no distance setting moved it.
- **The spawner fills whatever it is given.** At 150, 300 and 450 slots the pool was full within
  seconds. Capacity sets density; 0.1's doubled spawn rate only churned the pool faster and fired the
  batch cull more often. 0.2 returns it to stock.
- **450 far peds broke physics on the test machine.** With the pool at 438 of 450, peds and the
  player jittered vertically and fell through the map, which is what a starved frame budget does to
  the collision step. 300 ran clean for a full session and is the shipped value.
- **Distance settings above the spawn band do nothing you can see.** Once the batch cull no longer
  takes visible peds, the crowd's front edge is where the spawner stops placing them, 105 m in stock.
  130 and 160 m looked identical until the spawn band moved with them.
- **Conversions are not despawns.** The two largest remaining callers replace a far ped with a full
  ped at about 30 m and back. The replacement stands where the original did.
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
3. Launch. `popctl.log` records every patch attempt and its outcome.

To uninstall, delete both files. Nothing is written to disk by the plugin and no game file is modified.
Upgrading from 0.1: replace both files; the old `FarKeepMetres` key is still read as
`HiddenKeepMetres`.

## Verifying

`popctl.log` is the source of truth. These lines mean it worked:

```
pools: far pool 150 -> 300
pools: ped records 270 -> 420
patched: visible 130 m, hidden 130 m, near 130 m
pool cull: 0x738430 replaced; off-camera far peds go first, on-camera ones are never taken
pools: peds 120 x 3824 bytes, far peds 300 x 944 bytes, ped records 420 x 400 bytes
```

If any is missing, the log names the check that failed. `TraceRemovals = 1` then writes
`popctl_trace.log`, one line per deleted ped with the path that made it. It is how everything above
was measured and the first thing to turn on if you think popctl is not doing what it says.

## Configuration

`popctl.ini` is commented in full. `FarPedPool` is the setting that matters and 300 is the tested
value. `VisibleKeepMetres`, `HiddenKeepMetres` and `NearKeepMetres` ship equal at 130 so that pool
pressure, not a fixed radius, decides what survives behind you. The `[Pokes]` section takes raw
`RVA,type,stock,new` entries for the vehicle statics and the ped spawn band, and a value is written
only while the address still reads its stock value.

## Limitations

These are the boundaries of what was tested. Nothing outside them should be assumed to work.

- **Complete Edition 1.2.0.59 only.** Every address is a hardcoded RVA for that exact build. On any
  other version the checks fail, nothing is patched, and the log says so.
- **The full-ped pool is not grown.** The 120 real peds within about 30 m peaked at 111 during play.
  Density close to the player does not change. Its dependents were not enumerated.
- **Behind you, the crowd thins with distance.** The pool is finite; when it is full the farthest
  off-camera peds go first. Every view being ready needs more slots than the frame budget allowed.
- **The vehicle pool cannot be grown this way.** Raising it from 140 to 200 with the car budget at
  150 crashed after three minutes with the CPU jumping into a data address
  (`data/MiniDump_20260915_vehpool200.dmp`), the signature of a 140-entry table indexed by vehicle
  slot. Traffic stays bounded by the 110-car budget.
- **Interiors are unaffected.** Subway stations and other interiors are populated by scenario points
  and the popcycle interior column, neither touched.
- **Texture streaming is out of scope.** Far peds past roughly 100 m draw untextured. Stock deleted
  them before you could see it. Lower `VisibleKeepMetres` if that bothers you more than crowd depth.
- **One machine, one mod stack.** A camera flythrough with the player teleported along it for the
  numbers, play on Star Junction for the rest, FusionFix loaded. Frame rate was recorded, not
  characterised.
- **The "seen" flag is inferred.** The per-ped byte at `+0x142` behaves like a has-been-seen flag
  and is treated as one.

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
