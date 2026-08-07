# Ranked Leagues OBS Controller

Script/app to run seperatly to obs for easier control  
Replacement for tournament tool

### Running via python

`pip install -r requirements.txt`  
`py main.py`

### Running via exe

Open OBSController.exe (not released as of 07/08/2026)

## Setup
 - What the element name should be
    - Notes

### Recurring elements
---
These are to be made once and copy and pasted everywhere needed to create links between so changing one changes them all.
If any number of elements have the same name, they are already linked.

 - League
    - Text element for league number
 - Seed
    - Text element for seed number
 - Week
    - Text element for week number
    - Can rename 'week numer'
 - Big Leaderboard
    - browser source for player by player scores

### MAINSTREAM
---
 - items 
    - Browser source for inventory display
    - Set transform size to 330x330 and no crop
    - Set properties width and height to 330
    - Add `#info_container { display: none; }` to custom css
    - Delete/Disable 'Scroll' filter

### COMMENTATORS
---
 - comm2
    - Text element for commentator 2's name
    - Can rename 'comm 2'
 - commimg1
    - Image element for commentator 1's pfp
    - Can enable and rename image from default
 - commimg2
    - Image element for commentator 2's pfp
    - Can enable and rename image from default
 - lb
    - Browser source for top 5 lb

### LEADERBOARD
---
 - MATCH WINNER
    - Browser source for match by match winners

## Todos
auto player count  
auto fastest time