# ElementalOverhaul

Hitting something with a multi-element weapon in vanilla Valheim stacks one big particle cloud and one glow light per element on the target. With three elements it's a blur.

ElementalOverhaul replaces those clouds with effects drawn **on the creature's body**:

| Fire | Frost | Poison |
|---|---|---|
| ![Fire](https://raw.githubusercontent.com/dev-kreg/ValheimElementalOverhaul/main/docs/fire.gif) | ![Frost](https://raw.githubusercontent.com/dev-kreg/ValheimElementalOverhaul/main/docs/frost.gif) | ![Poison](https://raw.githubusercontent.com/dev-kreg/ValheimElementalOverhaul/main/docs/poison.gif) |
| **Spirit** | **Steam (fire + frost)** | **Ragnarok (all five)** |
| ![Spirit](https://raw.githubusercontent.com/dev-kreg/ValheimElementalOverhaul/main/docs/spirit.gif) | ![Steam](https://raw.githubusercontent.com/dev-kreg/ValheimElementalOverhaul/main/docs/steam.gif) | ![Ragnarok](https://raw.githubusercontent.com/dev-kreg/ValheimElementalOverhaul/main/docs/ragnarok.gif) |

| Element | Look |
|---|---|
| Fire | The game's own flames licking off the body, charred skin, smouldering heat patches, flickering firelight |
| Frost | A cold tint, a frost crust on upward faces, fine ice cracks, slow glints, falling flakes |
| Poison | Wandering veins with pulses travelling up the body, swelling and popping bubbles, drips |
| Lightning | Jagged arcs crawling over the body in short bursts, with the creature's light flashing in sync |
| Spirit | A hollow, darkened body with a teal rim and rising wisps |

Each element uses a different part of the look (surface, glow, rim, bursts), so several at once still read clearly. Stacked elements share one brightness budget, one particle budget and one light.

## Combos

Two elements together get their own effect instead of a blend. Each can be switched off in the config.

| Combo | Elements |
|---|---|
| Steam | fire + frost |
| Overload | fire + lightning |
| Toxic Burn | fire + poison |
| Ghost Fire | fire + spirit |
| Conductive Ice | frost + lightning |
| Frozen Veins | frost + poison |
| Wraith Chill | frost + spirit |
| Corrosive Sparks | lightning + poison |
| Soul Lightning | lightning + spirit |
| Blight | poison + spirit |

All five elements on one creature trigger **Ragnarok**: a darkened body split by fractures cycling through every element's colour, with shockwave rings rising up the body.

## Configuration

Everything lives in `BepInEx/config/ElementalOverhaul.cfg` (or the r2modman config editor), in sections `Global`, `Fire`, `Frost`, `Poison`, `Lightning`, `Spirit` and `Combos`: colours, brightness, pattern sizes, speeds, particle counts and more. **Changes apply in game as soon as the file is saved**, no restart needed.

Useful ones:
- `General.Mode`: `Overhaul` (default) or `Quiet`, which keeps the vanilla effects but makes them smaller. Needs a restart.
- `General.LightMultiplier`: how bright the creature's glow light is.
- `Global.ShellCount`: layers drawn just above the skin for flames, ice, haze and aura. Each one costs an extra draw of the creature; set 0 if big fights get slow.
- `Combos.Enabled`, `Combos.Replace`, and an `Enabled` switch per combo.

## Compatibility

- Purely visual and client-side. Safe in multiplayer; other players don't need it.
- Windows (DirectX 11 and Vulkan), native Linux (Vulkan), and Linux through Proton.
- macOS: the skin effects aren't available; particles and light still work.
- Draugr and Seekers have meshes the game doesn't allow emitting from, so their particles come from around the body instead of its surface.

## Feedback

This is a beta. If an effect looks wrong on a particular creature or in a particular light, a screenshot helps a lot. Source and issues: https://github.com/dev-kreg/ValheimElementalOverhaul
