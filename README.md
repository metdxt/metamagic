# Metamagic


<table>
<tr>
<td width="128px">

![](./logo.png)

</td>

<td>

_Advancing blender to godot pipeline with metadata!_

</td>
</tr>
</table>

**Metamagic** is a handy toolkit that bridges **Blender** and **Godot 4** by letting you tag your Blender objects with special metadata that Godot understands. No more manually setting up physics or bone attachments every time you re-import your models—configure it once in Blender, and Metamagic handles the rest automatically.

> ⚡ **The magic happens automatically**—just export from Blender and watch Godot do the heavy lifting!

---

## Features

### 🦴 Bone Attachments

Ever wanted to attach a sword, helmet, or any prop to a specific bone in your character's skeleton? Metamagic makes this super simple:

1. **Select your object** in Blender (the mesh, empty, or whatever you want to attach)
2. **Open the Metamagic panel** (N-panel in the 3D viewport)
3. **Pick the armature** and **bone** you want to attach to
4. **Export** to Godot
5. **Boom!** The object is now parented to a `BoneAttachment3D` node in Godot, following the bone animation perfectly

This is perfect for things like:
- Weapons attached to hands
- Accessories attached to heads
- Props attached to specific body parts
- UI elements that need to follow bone movement

### 🌊 Automated Jiggle Physics

Make your character's hair, tails, clothes, or floppy ears bounce naturally without writing a single line of code in Godot:

1. **Configure in Blender:** Select your armature, open the **Metamagic** panel (N-Panel), and set up your jiggle chains
2. **Export:** Save as `.blend` or export to gltf
3. **Done:** Godot automatically generates physics nodes with your exact settings (Stiffness, Drag, Gravity, etc.)

![Jiggle Physics Demo](./demo_screenshots/demo_jiggle.png)

### 🔄 Rotation Chain Utilities

Create bone rotation constraints with a single click—great for additive animations or procedural stuff:

1. **Select Bones:** Go to Edit Mode and pick a chain of bones (at least 2) in your armature
2. **Create Chain:** Hit the "Create Rotation Chain" button in the **Utilities** section
3. **Done:** Metamagic adds Copy Rotation constraints to each bone (except the topmost one), all set to LOCAL space for nice additive rotations

**Smart features:**
- Automatically finds the topmost bone in your selection
- Follows the bone hierarchy from parent to child
- Warns you if it detects branching (so you don't get weird results)
- Updates existing constraints instead of making duplicates

---

## Installation

### Download

Grab the latest release from the [GitHub Releases page](https://github.com/metdxt/metamagic/releases). You'll get two zips:

- **`metamagic_blender.zip`** - The Blender addon
- **`metamagic_godot.zip`** - The Godot addon

### 1. Blender Setup

1. Open Blender and hit **Edit > Preferences**
2. Click the **Add-ons** tab
3. Hit **Install...** and pick `metamagic_blender.zip`
4. Check the box next to **Metamagic** to enable it

**Quick test:**
- Select an armature
- Press `N` to open the sidebar
- Look for the **Metamagic** tab—should be there!

### 2. Godot Setup

1. Open your Godot project
2. Extract `metamagic_godot.zip` (or just grab the `metamagic` folder inside)
3. Drop it into your project's `addons/` folder
4. Go to **Project > Project Settings > Plugins**
5. Toggle on **Metamagic**

**Quick test:**
- Import a `.blend` or `.gltf` that you exported from Blender with Metamagic metadata
- Check that your physics nodes or bone attachments showed up automatically

**Note:** If you had assets in your project before installing Metamagic, you'll need to reimport them for the magic to happen. New imports work automatically—no extra steps needed!

---

## Quick Start Guide

### Setting Up Bone Attachments

Want to attach a sword to your character's hand?

1. Select your sword mesh in Blender
2. In the Metamagic panel, pick the character's armature
3. Choose the "Hand.R" (or whatever bone you want)
4. Export to Godot
5. Your sword is now properly parented and follows hand animation!

### Configuring Jiggle Physics

Making some bouncy... hair?

1. Select your character's armature
2. In the Metamagic panel, add a new chain
3. Set the start and end bones (e.g., "Hair_Start" to "Hair_End")
4. Tweak stiffness, drag, and gravity until it feels right
5. Export and watch it bounce in Godot!

---

## Tips & Tricks

- **Metadata sticks:** The configuration is saved in your Blender file, so you can always come back and tweak it
- **Non-destructive:** Metamagic doesn't modify your actual mesh or armature, it just adds metadata
- **Multiple chains:** You can have as many jiggle chains or bone attachments as you need
- **Export anywhere:** Whether you save as `.blend` or export to GLTF, Metamagic's metadata comes along for the ride

---

## Got Issues?

Found a bug or have a feature request? Open an issue on GitHub!
