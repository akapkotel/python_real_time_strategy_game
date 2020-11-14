## Real Time Strategy- _a RTS game written in Python_

#### INTRODUCTION:

This is my ambitious struggle against Python inefficiencies. An RTS game
made with Python 3.6 and Arcade 2.26 Library is my attempt to make
something what should **NOT** be done with this language.

I've decided to use Arcade library because of it's useful _SpriteLists_
concept and efficient way of drawing Sprites. All advantages and
disadvantages of Arcade library are available here:
[Arcade performance](https://arcade.academy/performance_tips.html)

#### INSTALLATION AND RUN:

For now, you have to clone or download this repository, create new
virtual environment, install requirements and run it by running
_game.py_ script in your IDE (e.g. PyCharm) or in terminal.

#### PLAYING:
To be done.

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
12. Simple permanent group of units are now 'saved' and player can
    activate them with 0-9 keys press.
13. Mouse-drag scrolling the map.
14. Small improvement to efficiency by spreading of many pathfinding
    calls for several update-frames, so no big lag when sending units to
    the opposite corner of the map.
15. Added queueing the pathfinding-requests and a Pathfinder changed to
    the Singleton.
16. Divided map to the Sectors to avoid visibility-tests between all
    Units and Buildings in game.
17. Scratch of Menu and user interface systems.
18. Units are now asking other units for pass if they are blocking their
    way.
19. Pathfinder can now find paths leading to the encircled areas or with
    entrances blocked by units.

#### TO BE DONE:
#### Minor:
1. Improve visibility-detection by 'communicating' what is seen between
   friendly Units which are very close to each other.
2. Improve collisions-avoidance to get rid off the
   diagonal-movements-collisions.
3. Display currently selected permanent units group number above each
   unit belonging to this group.
4. More efficient visibility-tests to avoid as many tests as possible.
5. Better collision-avoidance to replace tiles-reserving system -
   flocking maybe? How to make it working with pathfinding?
6. Minimap and teleporting to the map-locations by clickling on the
   minimap.
7. Pathfinder switching to paths searching with 'walkable' instead of
   'pathable' property in case where path would go through large group
   of units inside which it is impossible to make way for unit.
   Alternatively unit could go-around large groups without asking
   Pathfinder?

#### Major:
1. User-interface. (currently being developed)
2. Menu! (currently being developed)
3. AI (with finite-state=-machine?)
4. Saving and loading game (with shelve?)
5. Sounds and music (reimplement system from Pytanks for now?)
6. Multiplayer.
7. "Playing" section above.
8. Installer/executable for Windows and Linux.

Rafał "Akapkotel" Trąbski
