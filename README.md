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

**Metamagic** is a powerful dual-sided toolkit designed to bridge the gap between **Blender** and **Godot 4**. It allows you to attach game-logic metadata directly to your Blender objects and automates tedious setup routines during the import process.

> **Stop configuring physics manually every time you re-import.** Configure it once in Blender, and let Metamagic handle the rest.

---

## Features

### Automated Jiggle Physics

1.  **Configure in Blender:** Select your armature, open the **Metamagic** panel (N-Panel), and set up your jiggle chains (hair, tails, clothing).
2.  **Export:** Save as `.blend` or export to gltf.
3.  **Done:** Godot automatically detects the metadata and generates the necessary physics nodes with your exact settings (Stiffness, Drag, Gravity, etc.).

![Jiggle Physics Demo](./demo_screenshots/demo_jiggle.png)

---

## Installation

### Download

Download the latest release from the [GitHub Releases page](https://github.com/metdxt/metamagic/releases). You'll get two files:

- **`metamagic_blender.zip`** - The Blender addon
- **`metamagic_godot.zip`** - The Godot addon

### 1. Blender Side

1. Open Blender and go to **Edit > Preferences**
2. Navigate to the **Add-ons** tab
3. Click the **Install...** button
4. Select `metamagic_blender.zip` from the downloaded files
5. Enable **Metamagic** in the add-ons list by checking the box

**Verify Installation:**
- Select an armature in the 3D viewport
- Press `N` to open the N-panel
- You should see a new **Metamagic** tab

### 2. Godot Side

1. Open your Godot project
2. Extract `metamagic_godot.zip` (or copy the `metamagic` folder from inside it)
3. Navigate to your project's `addons/` directory
4. Paste the `metamagic` folder there
5. In Godot, go to **Project > Project Settings**
6. Navigate to the **Plugins** tab
7. Find **Metamagic** and enable it

**Verify Installation:**
- Import a `.blend` or `.gltf` file that was exported from Blender with Metamagic metadata
- Check that the imported scene has the expected physics nodes automatically generated based on your Blender configuration
- If there were any assets present in the project before metamagic was installed
you shall reimport them to let metamagic do it's work. For any new assets its automatic.
