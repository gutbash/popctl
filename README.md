# popctl

**Population control for GTA IV: The Complete Edition.** Keeps pedestrians and traffic alive at the
distances you choose, instead of the distances the engine hardcodes.

One plugin, one job. Engine audio slots are handled separately by
[revd](https://github.com/gutbash/revd); the two are independent and can be used together or apart.

## The problem

Crowds in GTA IV evaporate a short way behind you, and no amount of `popcycle.dat` editing or density
multiplier tuning fixes it. That is because neither of those is what removes them.

`CPopulation`'s removal loop walks every pedestrian each frame, takes the squared distance to the
player and compares it against a hardcoded constant: 6400 (80 m) on one branch, 225 (15 m) on the
other, chosen by a per-ped flag that appears to mean "on screen". Anything past that is deleted
outright. Raising density just means the game spawns more peds that it then deletes at the same
distance. Measured here, doubling and quadrupling the density multiplier and rewriting popcycle did
not change the ped count past 60 m by a single ped.

Both constants live in the shared constant pool, and the 60.0 sitting next to them has 119 other
users, so the constants themselves cannot be edited. `popctl` instead repoints the two instructions
that read them at floats inside its own DLL.

## What it changes

| Setting | Stock | What it controls |
|---|---|---|
| `FarKeepMetres` | 80 | Keep radius for peds the game considers on screen |
| `NearKeepMetres` | 15 | Keep radius for the other branch |
| `SpawnsPerFrame` | 8 | Ambient spawn attempts per frame |
| `[Pokes]` | various | Traffic generation band, removal distances, ambient car budget |

Nothing is written to disk. Every change is made in memory at runtime and disappears when you quit.

## Install

1. Have an ASI loader present. Ultimate ASI Loader as `dinput8.dll` is the usual one, and if you run
   FusionFix you already have it.
2. Drop `popctl.asi` and `popctl.ini` into your `GTAIV` folder, next to `GTAIV.exe`.
3. Launch. `popctl.log` appears next to the `.asi` and says what was patched.

To uninstall, delete both files.

## Configuration

Everything lives in `popctl.ini`, which is commented in full. The two settings worth knowing:

`FarKeepMetres` is the one you came for. 120 gives busy streets a block ahead of you. Every ped kept
alive costs main-thread CPU, so this is the first number to lower if your frame time suffers.

`SpawnsPerFrame` above 16 does nothing. The population manager only gathers up to 16 candidate spawn
nodes per frame, so 16 is the real ceiling and simply doubles the stock fill rate.

The `[Pokes]` section takes raw `RVA,type,stock,new` entries against the `CVehiclePopulation` block.
The shipped ones widen the traffic generation band and raise the ambient car budget. A poke is only
written if the address still reads its stock value, so a wrong entry is a no-op that gets logged
rather than a crash.

**Do not raise `VehMaxCars` towards 140.** The `CVehicle` pool has 140 slots, the factory returns NULL
past that, and the population code dereferences the result without checking. 160 crashes reliably.

## Limitations

These are the boundaries of what was tested. Nothing outside them should be assumed to work.

- **Complete Edition 1.2.0.59 only.** Every address here is a hardcoded RVA for that exact build.
  On any other version the signature check fails, nothing is patched, and the log says so. It will not
  damage anything, it simply will not do anything.
- **Costs CPU.** Keeping peds and cars alive is not free, and GTA IV's population work is on the main
  thread. Raising the radius trades frame time for crowds. How much depends entirely on your CPU and
  the rest of your mod stack.
- **Does not raise the pool ceilings.** This changes how long the game keeps what it spawned; it does
  not enlarge the ped or vehicle pools. `VehMaxCars` is bounded by the stock 140-slot pool.
- **One machine.** Developed and tested on a single install with FusionFix loaded through an ASI
  loader. Other mod stacks are untested.
- **Patches are in memory only.** Nothing on disk changes, and nothing persists after you quit.

## Building

Windows, Visual Studio 2022 with the x86 toolchain:

```
.\build.ps1            # produces popctl.asi
.\build.ps1 -Deploy    # and copies it into the game folder
```

Single translation unit, no dependencies beyond the Win32 SDK.

## License

MIT. See [LICENSE](LICENSE).
