### COMMENTATORS Scene
 - New image -> 'commimg1'
 - New image -> 'commimg2'
 - Rename 'comm 2' to 'comm2'
 - Copy 'League' to clipboard

### INTERMISSION Scene
 - Paste 'League'
 - Put it over the existing league counter
 - Delete the 'League #'

### LEADERBOARD Scene
 - Paste 'League'
 - Put it over the existing league counter
 - Delete the 'League #'

### Testing
 - Tools > Scripts
 - Python settings
   + Set location to where python is installed
   + Recommend 3.11
   + If you downloaded it from the microsoft store you have to uninstall and get from the installer from the website 
 - Run `py -m pip install requests pillow discord obsws_python` in CMD
 - Import 'mcrlobsscript.py' to obs
 - Test league, seed, week and seed type
 - Input discord bot script file path
 - Launch bot
 - Login to bot successfully
 - Connect to obs successfully
 - Try /set-commentators and /set-name-overrides

If anything went wrong please let me know (it usually shows a log window so send that too) > @dinotnt
