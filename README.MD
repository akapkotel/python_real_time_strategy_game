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
_pytanks.py_ script in your IDE (e.g. PyCharm) or in terminal.

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
7. Basic mouse-handling.
8. Scratch of the keyboard-handling.
9. Efficient replacements for the arcade.Spritelists allowing me to
   arbitrary 'activate', 'deactivate' updating and drawing some Sprites
   to avoid updating and drawing objects which are not on the screen.
10. Basic - distance and geometry-based - detection of which Sprites see
    each other.
11. Alternative scheduling calls system to work with the (to be done)
    saving and loading game.

#### TO BE DONE:
#### Minor:
1. Improve visibility-detection by 'communicating' what is seen between
   friendly Units which are very close to each other.
2. Improve collisions-avoidance to get rid off the
   diagonal-movements-collisions.

#### Major:
1. Installer/executable for Windows and Linux.
2. AI (with finite-state=-machine?)
3. Saving and loading game (with shelve?)
4. Sounds and music
5. Multiplayer.
6. "Playing" section above.

Rafał "Akapkotel" Trąbski
