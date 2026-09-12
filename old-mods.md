Old Mods

Researched against Nexus/GitHub/forum posts for compatibility with Skyrim AE 1.7.104 + SKSE64 2.3.1 on 2026-09-12.
SKSE-plugin (DLL) mods actually break on game updates until recompiled, so those got real searches.
Pure-content mods (textures, meshes, ESP/ESL-only quest/gameplay content, no compiled code) have no
game-version dependency at all, so they're bucketed as working based on that, not an individual forum check.

## Confirmed working on 1.7.104

- [x] Achievements Mods Enabler SE-AE (245)
- [ ] (Part 1) Engine Fixes for 1.6.1170 and newer (17230)
- [ ] (Part 2) Engine Fixes - skse64 Preloader and TBB Lib (17230)
- [x] All in one Address Library (Anniversary Edition) (32444)
- [x] Alternate Start - Live Another Life (272)
- [x] Alternate Start -- New Beginnings (4939)
- [ ] Animation Queue Fix (82395)
- [x] Better Jumping AE (18967)
- [x] DllLoader (3619) -- explicitly doesn't use SKSE, just loads DLLs from a folder
- [x] Experience (17751)
- [x] Instantly Skip Dialogue NG (89163)
- [ ] JContainers SE (16495)
- [x] powerofthree's Tweaks (51073)
- [x] Skyrim Script Extender (SKSE64) (silverlock.org)
- [x] SkyUI_5_2_SE (12604)
- [x] Sound Record Distributor (77815)
- [x] Unofficial Skyrim Special Edition Patch (USSEP) (266)

### Confirmed working -- pure content, no compiled code (textures/meshes/ESP-ESL only)

- [ ] A Quality World Map - Classic with All Roads (5804)
- [ ] A Quality World Map - Clear Map Skies (variant) (ID unrecovered)
- [ ] Apocalypse - Ordinator Compatibility Patch (1090)
- [ ] Apocalypse 10.2.2 (1090)
- [ ] Audio Overhaul for Skyrim (ID unrecovered)
- [ ] Bandit Lines Expansion (63733)
- [ ] BarenziahQuestMarkers SSE (ID unrecovered)
- [ ] Blended Roads (8834)
- [ ] Book Covers Skyrim (901)
- [ ] Cathedral - 3D Mountain Flowers (41312)
- [ ] Cathedral - Water (22962)
- [ ] Cutting Room Floor (276)
- [ ] Deadly Spell Impacts v1.9 (12939)
- [ ] Environs - Abandoned Abodes (82410)
- [ ] Environs - Hroggar's House (83457)
- [ ] Environs - Kolskeggr (78477)
- [ ] Environs - Master Plugin (91160)
- [ ] Environs - Riften Warehouse (88024)
- [ ] Environs - The Greenwood Shack (73732)
- [ ] Environs - The Ruined Tundra Farmhouse (72981)
- [ ] Environs - The Shrines of Talos (85141)
- [ ] Environs - The Western Watchtower (76261)
- [ ] Extended Encounters ESL (44810)
- [ ] Face Discoloration Fix SE (42441)
- [ ] Follower Trap Safety (2755)
- [ ] Footprints 1.6.1 (3808)
- [ ] Fuz Ro D'oh (15109)
- [ ] Guard Dialogue Overhaul - ESL (22075)
- [ ] Happy Little Trees (50961)
- [ ] Hearthfire Multiple Adoptions and Custom Home Support SE (3862)
- [ ] Holidays v2_20 Alpha 1 (1533)
- [ ] Honed Metal (61015)
- [ ] Hvergelmir's Aesthetics - Beards 5.0.1 (1067)
- [ ] Immersive Citizens - AI Overhaul (ID unrecovered)
- [ ] Legacy of the Dragonborn Patches (Official) (30980)
- [ ] Legacy of the Dragonborn V6 (11802)
- [ ] Morningstar 1.4.0 (22298)
- [ ] Obsidian Weathers - 1.07a (12125)
- [ ] Opulent Thieves Guild (931)
- [ ] Ordinator 9.31.0 (1137)
- [ ] Point The Way (352)
- [ ] Quick Light SE (12633)
- [ ] Relationship Dialogue Overhaul - RDO Final (1187)
- [ ] Remember Lockpick Angle (26838)
- [ ] Ruins Clutter Improved SE Mod Manager (5870)
- [ ] RUSTIC CLOTHING - Special Edition - 2K-1K (4703)
- [ ] Sleeping Expanded (59250)
- [ ] SMIM SE (659)
- [ ] The Eyes of Beauty SSE (16185)
- [ ] The Gildergreen fix (128828)
- [ ] The Paarthurnax Dilemma (365)
- [ ] Thunderchild v411 (1460)
- [ ] Unlimited Bookshelves (2885)
- [ ] Unlimited Training (774)
- [ ] Unread Books Glow SSE 2.2.1 (1296)
- [ ] Use Those Blankets (75481)
- [ ] Vanilla hair remake (63979)

## Unsure if working on 1.7.104

- [ ] Actor Limit Fix - Anniversary Edition (1.6.629.0 and later) (32349) -- ongoing compat discussions, some users needed newer address library
- [ ] Auto Parallax (79473) -- no compat info found
- [ ] Community Shaders (86492) -- as of late Aug 2026 hadn't picked up 1.7.x branch support yet
- [ ] eFPS - Exterior FPS boost (54907) -- no compat info found
- [ ] FISS (ID unrecovered) -- no compat info found
- [ ] Immersive Equipment Displays (62001) -- SKSE plugin, no explicit confirmation found
- [ ] LeanWolfs Better-Shaped Weapons Installer v2.1.03 SE (2017) -- no compat info found
- [ ] MCM Helper (53000) -- no compat info found
- [ ] Nemesis Unlimited Behavior Engine (60033) -- "should work" per recent reports but not rigorously tested, some need a compatibility patch
- [ ] NOFF No Friendly Fire v1.3.7.1 (54527) -- SKSE-dependent since v1.4, no explicit confirmation found
- [ ] PapyrusUtil AE SE - Scripting Utility Functions (13048) -- no compat info found
- [ ] Precision (72347) -- unofficial CommonLibSSE-NG builds target 1.7.x but official status unclear
- [ ] RaceMenu (ID unrecovered) -- updates lag behind game version, only experimental builds reported
- [ ] Realistic Ragdolls and Force SE (1439) -- no compat info found
- [ ] Security Overhaul SKSE - Add-ons (59529) -- no compat info found
- [ ] Security Overhaul SKSE - Lock Variations (58224) -- no compat info found
- [ ] Security Overhaul SKSE - Regional Locks (62781) -- no compat info found
- [ ] Simple Dual Sheath for 1.6.629 and newer (50049) -- no explicit 1.7.104 confirmation found
- [ ] Spell Perk Item Distributor (36869) -- actively maintained but no explicit 1.7.104 confirmation found
- [ ] SSE Display Tweaks (34705) -- SKSE plugin, no compat info found
- [ ] TrueHUD (62775) -- updated Aug 31 2026 (after the game update) but no explicit confirmation found
- [ ] Unlimited Fast Travel for 1.6.629 and newer (37889) -- no explicit 1.7.104 confirmation found

## Confirmed NOT working on 1.7.104

- [ ] Compass Navigation Overhaul (74484) -- explicitly reported broken on 1.7.x; author's own advice is to downgrade to 1.5.97 or 1.6.1170
- [ ] Infinity UI (74483) -- needs an update for the new SKSE/address library forms after the 1.7.99 update; Compass Navigation Overhaul and Local Map Upgrade depend on it
