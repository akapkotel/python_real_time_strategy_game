## Real Time Strategy- _a RTS game written in Python_

#### INTRODUCTION:

This is my ambitious struggle against Python inefficiencies. An RTS game
made with Python 3.6 and Arcade 2.26 Library is my attempt to make
something what should **NOT** be done with this language.

I've decided to use Arcade library because of useful _SpriteLists_
concept and efficient way of drawing Sprites. All advantages and
disadvantages of Arcade library are available here:
[Arcade performance](https://arcade.academy/performance_tips.html)

#### INSTALLATION AND RUN:

For now, you have to clone or download this repository. Then create new
virtual environment, install requirements and run it by running
_game.py_ script in your IDE (e.g. PyCharm) or in terminal.

#### PLAYING:
To be done.

![Menu](./screenshots/menu.png)

![Game Mode Menu](./screenshots/game_mode_selection.png)

![Game](./screenshots/actual_game.png)

### WHAT IS DONE:
1. Window and Views as different 'states' of the game.
2. Pathfinding with my A* implementation using PriorityQueue with my
   efficiency improvement: set of elements contained in PriorityQueue
   for faster lookups.
3. Simple - map-nodes-based - collision avoidance (buggy!).
4. Simple debugging logic.
5. Pausing game logic.
6. Finding files by their names without any paths-constants etc.
7. Basic mouse-handling: selecting, unselecting, giving move-orders to
   Units.
8. Scratch of the keyboard-handling.
9. Efficient replacements for the arcade.Spritelists allowing me to
   arbitrary 'activate', 'deactivate' updating and drawing some Sprites
   to avoid updating and drawing objects which are not on the screen.
10. Basic - distance and geometry-based - detection of which Sprites see
    each other.
11. Alternative scheduling calls system to work with the (to be done)
    saving and loading game.
12. Simple permanent group of units is now 'saved' and player can
    activate them with 0-9 keys press.
13. Mouse-drag scrolling the map.
14. Small improvement to efficiency by spreading of many pathfinding
    calls for several update-frames, so no big lag when sending units to
    the opposite corner of the map.
15. Added queueing the pathfinding-requests, and a Pathfinder changed to
    the Singleton.
16. Divided map to the Sectors to avoid visibility-tests between all
    Units and Buildings in game.
17. Scratch of Menu and user interface systems.
18. Units are now asking other units for pass if they are blocking their
    way.
19. Pathfinder can now find paths leading to the encircled areas or with
    entrances blocked by units.
20. Working sounds: music background tracks, sound-effects,
    ui-sound-effects.
21. Display currently selected permanent units group number above each
   unit belonging to this group.
22. Units are now 1x8 or 8x8 (tanks with turrets) sprite-sheets, so they
    can face 8 directions (and other 8 directions for turrets). Each
    Unit can be spawned in many, various colors, depending on the
    player's choice.
23. Optimized visibility-detection, to reduce cpu overhead.
24. Units automatically moving towards detected enemies out of their
    attack range.
25. Subdivided FogOfWar SpriteList to optimize FoW updates performance.
26. Shot, hit and destruction graphic effects and sounds.
27. Simple minimap showing current viewport position and revealed map
    area.
28. Vehicles leave tires/tracks traces on the ground.
29. When Vehicles are destroyed, they leave wrecks.
30. Implemented pooling to boost Explosions efficiency.
31. Implemented in-game timer displaying how much time passed since game started.
32. Implemented new game-loading from file system. 
33. Added playlists for background music tracks.
10.06.2021:
34. Improved mini-map: better resolution, no more ugly big rectangles!
35. Saving Trees works now!
36. Loading menu with auto-updating list of existing save-files.
28.06.2021:
37. UI for Buildings and Units-production added.
38. Player can now produce new units.
39. Soldiers can enter end leave Buildings.
40. UI displays amount of resources, player has.
17.03.2023:
41. New UI with icons for resources and units and buildings construction panels.
42. Prettier Fog Of War without sharp edges.
43. Units are now rotated in 16 directions instead of 8.
44. CPU-player can now build Units, having enough resources and proper factories.
45. Added two more units prototypes - Truck and APC.
46. Minimap and teleporting to the map-locations by clickling on the
   minimap (was added long time ago, but I missed noticing it).

#### TO BE DONE:
#### Minor:
1. Improve visibility-detection by 'communicating' what is seen between
   friendly Units which are very close to each other.
2. Improve collisions-avoidance to get rid off the
   diagonal-movements-collisions.
3. Better collision-avoidance to replace tiles-reserving system -
   flocking maybe? How to make it working with pathfinding?
4. Units-radiochatter sounds - DONE. Battle sounds.
5. Skirmish mission customisation submenu (this is the only available
   game mode for now).
6. Playlist for background music tracks - DONE.
7. Better Ai for Units autonomous behaviour.
8. Flocking for Soldier class.
9. Implement Jump Point Search to optimize A* performance.
10. Less cpu-heavy VehicleThreads.
11. Nicer MiniMap without ugly rectangles representing discovered area - DONE.

#### Major:
1. User-interface. (currently being developed)
2. Menu! (currently being developed)
3. AI (with finite-state=-machine?)
4. Saving and loading game (with shelve?) - DONE
5. Sounds and music - DONE
6. Multiplayer.
7. "Playing" section above.
8. Installer/executable for Windows and Linux.
9. Docker image.

### Gameplay mechanics:
1. Many various resources consumed to produce units and maintain
   infrastructure and extracted in different ways.
2. Technological advancement system - researching new technologies
   allows player to build better units and buildings.
3. Conscription system: to build units, especially infantry, player
   needs to create recruitments facilities near civilian villages and
   protect them from enemies.
4. Supply-transportation and storage system. Units do not have infinite
   ammunition and fuel and require to be resupplied from base by the
   supply-transporting vehicles. Protecting supply-lines is required.

Rafał "Akapkotel" Trąbski
