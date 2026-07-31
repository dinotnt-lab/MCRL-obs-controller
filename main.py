import customtkinter as ctk
import json
import re
from tkinter import filedialog
import obsws_python
import requests
from PIL import Image, ImageDraw
from io import BytesIO
from pathlib import Path
import CTkMessagebox
import threading

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

downloads = Path.home() / 'downloads'

try:
    with open('settings.json', 'r') as f:
        settings = json.load(f)
except FileNotFoundError:
    settings = {}

app = ctk.CTk()
app.geometry("550x900+100+100")
app.title("MCRL OBS Tool")

playerlist = None
streamingplayerlist = []
obs = None

def run_thread(function):
    threading.Thread(target=function, daemon=True).start()

def validate_league(value):
    if value.isdigit():
        if 8 > int(value) > 0:
            return True
    if value == '':
        return True
    return False

def validate_number(value):
    return value == "" or value.isdigit()

validate_league_cmd = app.register(validate_league)
validate_number_cmd = app.register(validate_number)

# region setup utils

# def loadspecfile():
#     spec_file_path = filedialog.askopenfilename(
#         title="Select spectate_match.json file",
#         filetypes=[("JSON", "*.json")]
#     )
#     if spec_file_path:
#         settings['spec_file'] = spec_file_path
#         spec_file_status_label.configure(text='Found')
#         spec_file_button.configure(fg_color='green', hover_color='dark green', state='disabled')

def loadplayerfile():
    try:
        global playerlist, streamingplayerlist

        playerlistpath = filedialog.askopenfilename(
            title="Select .ranked file",
            filetypes=[("Ranked files", "*.ranked")]
        )

        if playerlistpath:
            with open(playerlistpath, "r") as f:
                data = json.load(f)

            league = playerlistpath.split('mcrl_')[1].split('_')[0]
            week = playerlistpath.split('mcrl_')[1].split('_')[1].replace('.ranked', '')

            streamingplayerlist.clear()

            league_entry.set(league)
            week_entry.set(week)

            for player in data:
                username = player.get("twitch_username")

                if username:
                    if "https" in username or "twitch.tv" in username:
                        match = re.match(
                            r"^(?:https?://)?(?:www\.)?twitch\.tv/([A-Za-z0-9_]+)/?$",
                            username
                        )

                        if match:
                            streamingplayerlist.append({'ign': player.get('ign'), 'twitch': match.group(1), 'element': None, 'uuid': None, 'displayname': player.get('display_name')})
                    else:
                        streamingplayerlist.append({'ign': player.get('ign'), 'twitch': username, 'element': None, 'uuid': None, 'displayname': player.get('display_name'), 'achievement': ''})

            for player in streamingplayerlist:
                player_frame = ctk.CTkFrame(streams_frame)
                player_frame.pack(padx=5, pady=2)

                element = ctk.CTkButton(player_frame, text=f'{player["ign"]}\n', command=lambda p=player: selectstream(p))
                element.pack(padx=5, pady=2)

                player['element'] = element
                player['frame'] = player_frame

            file_status_label.configure(text=f'Loaded {len(streamingplayerlist)} streamers')
            playerlistbutton.configure(fg_color='green', hover_color='dark green')
            updateobs()
    except Exception as e:
        file_status_label.configure(text=e)

def connectobs():
    global obs
    try:
        obs = obsws_python.ReqClient(host="localhost", port=4455, password=obs_password_entry.get(), timeout=3)
        obs_status.configure(text = 'Success')
        obs_button.configure(fg_color='green', hover_color='dark green', state='disabled')

    except ConnectionRefusedError:
        obs_status.configure(text = 'OBS websockets not enabled or port changed (return to default). Tools > Websocket Server Settings')
        return
    
    except Exception as e:
        obs = None
        error = str(e).lower()

        if "password" in error:
            obs_status.configure(text = "Incorrect or missing password")
        elif "failed" in error:
            obs_status.configure(text = "Incorrect or missing password")
        else:
            obs_status.configure(text = f'Error: `{e}`')
        return

setupComplete = False

def updateobs():
    global setupComplete, obs
    if streamingplayerlist == []:
        update_status_label.configure(text='Missing Player File')
        return
    if not bot_entry.get():
        update_status_label.configure(text='Missing Discord Bot Token')
        return
    elif not api_entry.get():
        update_status_label.configure(text='Missing MCSR API Key')
        return
    elif not ign_entry.get():
        update_status_label.configure(text='Missing MCSR ign')
        return
    # elif not settings.get('spec_file'):
    #     update_status_label.configure(text='Missing spectate_match.json')
        return
    if obs is None:
        update_status_label.configure(text="OBS not connected")
        return
    
    if not settings.get('obs_password') and obs_password_entry.get():
        settings['obs_password'] = obs_password_entry.get()
    if not settings.get('ranked_api_key'):
        settings['ranked_api_key'] = api_entry.get()
    if not settings.get('discord_token'):
        settings['discord_token'] = bot_entry.get()
    if not settings.get('ign'):
        settings['ign'] = ign_entry.get()

    with open('settings.json', 'w') as f:
        json.dump(settings, f)

    obs.set_input_settings('League', {'text': 'League ' + league_entry.get()}, True)
    obs.set_input_settings('Week', {'text': 'Week ' + week_entry.get()}, True)
    obs.set_input_settings('Seed', {'text': 'Seed ' + seed_entry.get()}, True)

    for source in ['Big Leaderboard', 'MATCH WINNER', 'lb']:
        obs.set_input_settings(source, {"url": f'https://mscl.pages.dev/week/?week={week_entry.get()}&league={league_entry.get()}'}, True)

    commentators()
    obs.set_input_settings('comm1', {'text': comm1_name_entry.get()}, True)
    obs.set_input_settings('comm2', {'text': comm2_name_entry.get()}, True)
    setupComplete = True
    update_button.configure(fg_color='green', hover_color='dark green')

pcomm1 = ''
pcomm2 = ''

def commentators():
    run_thread(commentators_thread)


def commentators_thread():
    global pcomm1, pcomm2

    try:
        comm1 = comm1_entry.get()
        comm2 = comm2_entry.get()

        if comm1 == '':
            app.after(0, lambda: obs.set_input_settings('commimg1', {'file': ''}, True))
            app.after(0, lambda: comm1_name_entry.set(''))
            pcomm1 = ''

        elif comm1 != pcomm1:
            pcomm1 = comm1
            url = f"https://discord.com/api/v10/users/{comm1}"
            r = requests.get(url, headers={"Authorization": f"Bot {settings.get('discord_token')}"}, timeout=5)
            r.raise_for_status()
            data = r.json()

            name = data.get('global_name')
            avatar = data.get('avatar')

            filepath = circlify(f"https://cdn.discordapp.com/avatars/{comm1}/{avatar}.png?size=512", name)

            app.after(0, lambda: comm1_name_entry.set(name))
            app.after(0, lambda: obs.set_input_settings('commimg1', {'file': filepath}, True))

        if comm2 == '':
            app.after(0, lambda: obs.set_input_settings('commimg2', {'file': ''}, True))
            app.after(0, lambda: comm2_name_entry.set(''))
            pcomm2 = ''

        elif comm2 != pcomm2:
            pcomm2 = comm2
            url = f"https://discord.com/api/v10/users/{comm2}"
            r = requests.get(url, headers={"Authorization": f"Bot {settings.get('discord_token')}"}, timeout=5)
            r.raise_for_status()
            data = r.json()

            name = data.get('global_name')
            avatar = data.get('avatar')

            filepath = circlify(f"https://cdn.discordapp.com/avatars/{comm2}/{avatar}.png?size=512", name)

            app.after(0, lambda: comm2_name_entry.set(name))
            app.after(0, lambda: obs.set_input_settings('commimg2', {'file': filepath}, True))

    except Exception as e:
        app.after(0, lambda: update_status_label.configure(text=str(e)))

def circlify(url, name):
    global downloads
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()

    img = Image.open(BytesIO(resp.content)).convert("RGBA")
    img = img.resize((256,256))

    size = min(img.width, img.height)

    left = (img.width - size) // 2
    top = (img.height - size) // 2
    right = left + size
    bottom = top + size

    img = img.crop((left, top, right, bottom))

    scale = 4
    mask = Image.new("L", (size * scale, size * scale), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size * scale, size * scale), fill=255)
    mask = mask.resize((size, size), Image.Resampling.LANCZOS)

    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(img, (0, 0), mask)

    filepath = downloads / f"{name}-commentator-pfp.png"

    result.save(filepath)

    return str(filepath)

# endregion

players_in_room = []
split_updating = False
selectedstream = None

def selectstream(player):
    global selectedstream
    if selectedstream:
        selectedstream['element'].configure(fg_color='#1f6aa5')
    if selectedstream == player:
        selectedstream = None
        return
    selectedstream = player
    player['element'].configure(fg_color='blue')

selectedspot = None
selectedspotelement = None

def selectspot(spot, element):
    global selectedstream, selectedspot, selectedspotelement

    if selectedstream != None:
        obs.set_input_settings(
            'pov' + str(spot), 
            {'url': f'https://player.twitch.tv/?channel={selectedstream["twitch"]}&enableExtensions=true&muted=false&parent=twitch.tv&player=popout&quality=chunked&volume=0'}, 
            True
        )
        obs.set_input_settings(
            'pov' + str(spot) + 'name',
            {'text': selectedstream['displayname']},
            True
        )
        element.configure(text=selectedstream['ign'], fg_color='#1f6aa5')
        selectedstream['element'].configure(fg_color='#1f6aa5')
        selectedstream = None

    elif selectedspot != None:
        aurl = obs.get_input_settings('pov' + str(selectedspot)).input_settings['url']
        aname = obs.get_input_settings('pov' + str(selectedspot) + 'name').input_settings['text']

        burl = obs.get_input_settings('pov' + str(spot)).input_settings['url']
        bname = obs.get_input_settings('pov' + str(spot) + 'name').input_settings['text']

        obs.set_input_settings('pov' + str(spot), {'url': aurl}, True)
        obs.set_input_settings('pov' + str(spot) + 'name', {'text': aname}, True)

        obs.set_input_settings('pov' + str(selectedspot), {'url': burl}, True)
        obs.set_input_settings('pov' + str(selectedspot) + 'name', {'text': bname}, True)

        aign = ""
        bign = ""

        for streamer in streamingplayerlist:
            if streamer['twitch'] == aurl.replace('https://player.twitch.tv/?channel=', '').replace('&enableExtensions=true&muted=false&parent=twitch.tv&player=popout&quality=chunked&volume=0', ''):
                aign = streamer['ign']
            elif streamer['twitch'] == burl.replace('https://player.twitch.tv/?channel=', '').replace('&enableExtensions=true&muted=false&parent=twitch.tv&player=popout&quality=chunked&volume=0', ''):
                bign = streamer['ign']

        element.configure(text=aign)
        selectedspotelement.configure(text=bign, fg_color='#1f6aa5')

        selectedspotelement = None
        selectedspot = None
    else:
        element.configure(fg_color='blue')
        selectedspot = spot
        selectedspotelement = element

def clear():
    global selectedspot
    if selectedspot == None:
        return
    
    obs.set_input_settings('pov' + str(selectedspot), {'url': ''}, True)
    obs.set_input_settings('pov' + str(selectedspot) + 'name', {'text': ''}, True)

    if selectedspot == 1:
        x = view_1_button
    elif selectedspot == 2:
        x = view_2_button
    elif selectedspot == 3:
        x = view_3_button
    elif selectedspot == 4:
        x = view_4_button
    x.configure(text='', fg_color='#1f6aa5')

    selectedspot = None

sent_count_warning = False

def updatesplits():
    global split_updating
    if not split_updating:
        return

    if tabs.get() != 'Streams':
        app.after(2000, updatesplits)
        return

    run_thread(fetch_splits)

info = ['','','','','']
uuid_to_streamer = {}

ACHIEVEMENT_ORDER = {
    'Killed Dragon': 0,
    'Enter End': 1,
    'Eye Spy': 2,
    'Blind': 3,
    'First Rod': 4,
    'Fortress': 5,
    'War Pigs': 6,
    'Bastion': 7,
    'Nether': 8,
    'Hot Stuff': 9,
    'Iron Pickaxe': 10,
    'Iron': 11,
}

def reorder_streamer_buttons():
    global streamingplayerlist

    sorted_players = sorted(
        streamingplayerlist,
        key=lambda player: (
            ACHIEVEMENT_ORDER.get(player.get('achievement'), len(ACHIEVEMENT_ORDER)),
            player.get('ign', '').lower()
        )
    )

    for player in sorted_players:
        player['frame'].pack_forget()

    for player in sorted_players:
        player['frame'].pack(padx=5, pady=2)


def update_splits_display(data):
    global players_in_room, info, uuid_to_streamer

    if data['status'] == 'error':
        CTkMessagebox.CTkMessagebox(title='Alert', message=data['data']['error'], icon="warning")
        return

    apidata = data['data']
    players_in_room = apidata["players"]

    if apidata['status'] == 'counting' and 'Match Countdown Started' not in info:
        info = info[1:] + ['Match Countdown Started']
        info_label.configure(text='\n'.join(info))

    elif apidata['status'] == 'generate' and 'Match Generation Started' not in info:
        info = info[1:] + ['Match Generation Started']
        info_label.configure(text='\n'.join(info))

    elif apidata['status'] == 'running' and 'Match Started' not in info:
        info = info[1:] + ['Match Started']
        info_label.configure(text='\n'.join(info))

    elif apidata['status'] == 'idle':
        live_by_name = {
            player["nickname"]: player
            for player in players_in_room
        }

        uuid_to_streamer.clear()

        for streamer in streamingplayerlist:
            live = live_by_name.get(streamer["ign"])

            if live is None:
                streamer["achievement"] = ''
                streamer["element"].configure(text=f"{streamer.get('ign')}\nNot In Room")
                streamer["uuid"] = None
            else:
                uuid_to_streamer[live['uuid']] = streamer
                streamer["uuid"] = live.get('uuid')
                streamer["achievement"] = ''
                streamer["element"].configure(text=f"{streamer.get('ign')}\nIn Room")

    elif apidata['status'] == 'running':
        if uuid_to_streamer == {}:
            live_by_name = {
                player["nickname"]: player
                for player in players_in_room
            }
            for streamer in streamingplayerlist:
                live = live_by_name.get(streamer["ign"])
                if live is not None:
                    uuid_to_streamer[live['uuid']] = streamer

        shown = {}
        achievement_map = {'projectelo.timeline.dragon_death': 'Killed Dragon', 'story.enter_the_end': 'Enter End', 'story.follow_ender_eye': 'Eye Spy', 'projectelo.timeline.blind_travel': 'Blind', 'nether.obtain_blaze_rod': 'First Rod', 'nether.find_fortress': 'Fortress', 'nether.loot_bastion': 'War Pigs', 'nether.find_bastion': 'Bastion', 'story.enter_the_nether': 'Nether', 'story.lava_bucket': 'Hot Stuff', 'story.iron_tools': 'Iron Pickaxe', 'story.smelt_iron': 'Iron'}
        done = set()

        for timeline in apidata.get('timelines', []):
            streamer = uuid_to_streamer.get(timeline.get('uuid'))

            if streamer:
                ign = streamer.get('ign')
                previous = shown.get(ign)

                if previous is None or timeline.get('time') > previous.get('time'):
                    achievement = achievement_map.get(timeline.get('type'))
                    if achievement:
                        shown[ign] = timeline
                        streamer['achievement'] = achievement
                        streamer["element"].configure(text=f'{ign}\n{achievement}')
                        reorder_streamer_buttons()
                        if achievement not in done:
                            done.add(achievement)
                            info = info[1:] + [f"{achievement} by {streamer['ign']}"]
                            info_label.configure(text='\n'.join(info))

        for completion in apidata.get('completions', []):
            streamer = uuid_to_streamer.get(completion.get('uuid'))
            if streamer and streamer.get('frame') is not None:
                streamer['frame'].pack_forget()
                streamer['element'].configure(text=f"{streamer.get('ign')}\nComplete")
    

def fetch_splits():
    try:
        res = requests.get('https://api.mcsrranked.com/users/' + settings.get('ign') + '/live', headers={'Private-Key': settings.get('ranked_api_key')}, timeout=5)
        res.raise_for_status()
        data = res.json()

        app.after(0, lambda: update_splits_display(data))

    except Exception as e:
        app.after(0, lambda: update_status_label.configure(text=str(e)))

    finally:
        app.after(2000, updatesplits)

def tab_changed():
    global split_updating
    if tabs.get() == 'Streams' and not setupComplete:
        tabs.set('Setup')
        CTkMessagebox.CTkMessagebox(title='Incomplete Setup', message='Complete setup before continuing', icon="warning")
    elif tabs.get() == 'Streams':
        app.geometry("600x500")
        if not split_updating:
            split_updating = True
            updatesplits()
        else:
            split_updating = False
    elif tabs.get() == 'Setup':
        app.geometry("550x900")

tabs = ctk.CTkTabview(app, command=tab_changed)
tabs.pack(expand=True, fill="both", padx=15, pady=6)

setup_tab = tabs.add("Setup")
streams_tab = tabs.add("Streams")

# region setup
# Setup Header
title = ctk.CTkLabel(
    setup_tab,
    text="League Setup",
    font=ctk.CTkFont(size=24, weight="bold")
)
title.pack(pady=(15, 25))


# Player file section
file_frame = ctk.CTkFrame(setup_tab)
file_frame.pack(fill="x", padx=20, pady=5)

file_label = ctk.CTkLabel(
    file_frame,
    text="Player File:"
)
file_label.pack(side="left", padx=10, pady=5)

playerlistbutton = ctk.CTkButton(
    file_frame,
    text="Open Player File",
    command=loadplayerfile
)
playerlistbutton.pack(side="right", padx=10, pady=5)

file_status_label = ctk.CTkLabel(
    file_frame,
    text="",
    text_color='gray'
)
file_status_label.pack(side="right", padx=10, pady=5)

#spectator file
# spec_file_frame = ctk.CTkFrame(setup_tab)
# spec_file_frame.pack(fill="x", padx=20, pady=5)

# spec_file_label = ctk.CTkLabel(
#     spec_file_frame,
#     text="Spectate_match.json file:"
# )
# spec_file_label.pack(side="left", padx=10, pady=5)

# spec_file_button = ctk.CTkButton(
#     spec_file_frame,
#     text="Open Spectator File",
#     command=loadspecfile
# )
# spec_file_button.pack(side="right", padx=10, pady=5)

# spec_file_status_label = ctk.CTkLabel(
#     spec_file_frame,
#     text="",
#     text_color='gray'
# )
# spec_file_status_label.pack(side="right", padx=10, pady=5)


#OBS section
obs_frame = ctk.CTkFrame(setup_tab)
obs_frame.pack(fill='x', padx=20, pady=10)

obs_label = ctk.CTkLabel(
    obs_frame,
    text='Connect OBS:'
)
obs_label.pack(side="left", padx=10, pady=5)

obs_button = ctk.CTkButton(
    obs_frame,
    text='Connect to OBS',
    command=connectobs
)
obs_button.pack(side='right', padx=10, pady=5)

obs_status = ctk.CTkLabel(
    obs_frame,
    text='',
    text_color='gray'
)
obs_status.pack(side='right', padx=10, pady=5)


#obs password
obs_password_frame = ctk.CTkFrame(setup_tab)
obs_password_frame.pack(fill='x', padx=20, pady=5)

obs_password_label = ctk.CTkLabel(
    obs_password_frame,
    text='OBS password:'
)
obs_password_label.pack(side="left", padx=10, pady=5)

obs_password_entry = ctk.CTkEntry(
    obs_password_frame
)
obs_password_entry.pack(side='right', padx=10, pady=5)


# League section
league_frame = ctk.CTkFrame(setup_tab)
league_frame.pack(fill="x", padx=20, pady=10)

league_label = ctk.CTkLabel(
    league_frame,
    text="League #: (1-7)"
)
league_label.pack(side="left", padx=10, pady=5)

league_entry = ctk.CTkEntry(
    league_frame,
    validate='key',
    validatecommand=(validate_league_cmd, '%P')
)
league_entry.pack(side="right", padx=10, pady=5)


# Week section
week_frame = ctk.CTkFrame(setup_tab)
week_frame.pack(fill="x", padx=20, pady=10)

week_label = ctk.CTkLabel(
    week_frame,
    text="Week #:"
)
week_label.pack(side="left", padx=10, pady=5)

week_entry = ctk.CTkEntry(
    week_frame,
    validate="key",
    validatecommand=(validate_number_cmd, "%P")
)
week_entry.pack(side="right", padx=10, pady=5)


# seed section
seed_frame = ctk.CTkFrame(setup_tab)
seed_frame.pack(fill="x", padx=20, pady=5)

seed_label = ctk.CTkLabel(
    seed_frame,
    text="Seed #:"
)
seed_label.pack(side="left", padx=10, pady=5)

seed_entry = ctk.CTkEntry(
    seed_frame,
    validate="key",
    validatecommand=(validate_number_cmd, "%P")
)
seed_entry.pack(side="right", padx=10, pady=5)


# commentators section
comm1_frame = ctk.CTkFrame(setup_tab)
comm1_frame.pack(fill='x', padx=20, pady=5)

comm1_label = ctk.CTkLabel(
    comm1_frame,
    text="Commentator 1's discord ID:"
)
comm1_label.pack(side="left", padx=10, pady=5)

comm1_entry = ctk.CTkEntry(
    comm1_frame,
    validate="key",
    validatecommand=(validate_number_cmd, "%P")
)
comm1_entry.pack(side="right", padx=10, pady=5)

comm2_frame = ctk.CTkFrame(setup_tab)
comm2_frame.pack(fill='x', padx=20, pady=5)

comm2_label = ctk.CTkLabel(
    comm2_frame,
    text="Commentator 2's discord ID:"
)
comm2_label.pack(side="left", padx=10, pady=5)

comm2_entry = ctk.CTkEntry(
    comm2_frame,
    validate="key",
    validatecommand=(validate_number_cmd, "%P")
)
comm2_entry.pack(side="right", padx=10, pady=5)


comm1_name_frame = ctk.CTkFrame(setup_tab)
comm1_name_frame.pack(fill='x', padx=20, pady=5)

comm1_name_label = ctk.CTkLabel(
    comm1_name_frame,
    text="Commentator 1's name:"
)
comm1_name_label.pack(side="left", padx=10, pady=5)

comm1_name_entry = ctk.CTkEntry(
    comm1_name_frame
)
comm1_name_entry.pack(side="right", padx=10, pady=5)

comm2_name_frame = ctk.CTkFrame(setup_tab)
comm2_name_frame.pack(fill='x', padx=20, pady=5)

comm2_name_label = ctk.CTkLabel(
    comm2_name_frame,
    text="Commentator 2's name:"
)
comm2_name_label.pack(side="left", padx=10, pady=5)

comm2_name_entry = ctk.CTkEntry(
    comm2_name_frame
)
comm2_name_entry.pack(side="right", padx=10, pady=5)

# api key
api_frame = ctk.CTkFrame(setup_tab)
api_frame.pack(fill='x', padx=20, pady=5)

api_label = ctk.CTkLabel(
    api_frame,
    text='MCSR Ranked API key: (profile > settings)'
)
api_label.pack(side='left', padx=10, pady=5)

api_entry = ctk.CTkEntry(
    api_frame
)
api_entry.pack(side='right', padx=10, pady=5)

ign_frame = ctk.CTkFrame(setup_tab)
ign_frame.pack(fill='x', padx=20, pady=5)

ign_label = ctk.CTkLabel(
    ign_frame,
    text='Your MCSR ign: '
)
ign_label.pack(side='left', padx=10, pady=5)

ign_entry = ctk.CTkEntry(
    ign_frame
)
ign_entry.pack(side='right', padx=10, pady=5)

# bot key
bot_frame = ctk.CTkFrame(setup_tab)
bot_frame.pack(fill='x', padx=20, pady=5)

bot_label = ctk.CTkLabel(
    bot_frame,
    text='Discord bot key:'
)
bot_label.pack(side='left', padx=10, pady=5)

bot_entry = ctk.CTkEntry(
    bot_frame
)
bot_entry.pack(side='right', padx=10, pady=5)

#update frame
update_frame = ctk.CTkFrame(setup_tab)
update_frame.pack(fill='x', padx=20, pady=5)

update_label = ctk.CTkLabel(
    update_frame,
    text='Update OBS'
)
update_label.pack(side='left', padx=10, pady=5)

update_button = ctk.CTkButton(
    update_frame,
    text='Update',
    command=updateobs
)
update_button.pack(side='right', padx=10, pady=5)

update_status_label = ctk.CTkLabel(
    update_frame,
    text='',
    text_color='gray'
)
update_status_label.pack(side='right', padx=10, pady=5)

# endregion

# region streams
streams_frame = ctk.CTkFrame(streams_tab)
streams_frame.pack(fill="x", padx=20, pady=5, side='left')

info_obs_frame = ctk.CTkFrame(streams_tab)
info_obs_frame.pack(fill='x', padx=20, pady=5, side='right')

info_frame = ctk.CTkFrame(info_obs_frame)
info_frame.pack(fill='x', padx=20, pady=5)

info_title = ctk.CTkLabel(
    info_frame,
    text='Match Info',
    font=ctk.CTkFont(size=20)
)
info_title.pack(fill='x', padx=5, pady=5)

info_label = ctk.CTkLabel(
    info_frame,
    text='\n\n\n\n\n'
)
info_label.pack(fill='x', padx=5, pady=5)

obs_input_frame = ctk.CTkFrame(info_obs_frame)
obs_input_frame.pack(fill='x', padx=20, pady=5)

view_1_button = ctk.CTkButton(
    obs_input_frame,
    width=150,
    height=100,
    text='',
    command=lambda: selectspot(1, view_1_button)
)
view_1_button.pack(side='left', padx=10, pady=10)

right_view_frame = ctk.CTkFrame(obs_input_frame)
right_view_frame.pack(side='right', padx=10, pady=10)

view_2_button = ctk.CTkButton(
    right_view_frame,
    width=100,
    height=40,
    text='',
    command=lambda: selectspot(2, view_2_button)
)
view_2_button.pack(pady=5)

view_3_button = ctk.CTkButton(
    right_view_frame,
    width=100,
    height=40,
    text='',
    command=lambda: selectspot(3, view_3_button)
)
view_3_button.pack(pady=5)

view_4_button = ctk.CTkButton(
    right_view_frame,
    width=100,
    height=40,
    text='',
    command=lambda: selectspot(4, view_4_button)
)
view_4_button.pack(pady=5)

clear_button = ctk.CTkButton(
    info_obs_frame,
    text="Clear",
    command=clear
)

clear_button.pack()
# endregion

seed_entry.set(1)
if settings.get('obs_password'):
    obs_password_entry.set(str(settings.get('obs_password')))
if settings.get('ranked_api_key'):
    api_entry.set(str(settings.get('ranked_api_key')))
if settings.get('discord_token'):
    bot_entry.set(str(settings.get('discord_token')))
if settings.get('ign'):
    ign_entry.set(str(settings.get('ign')))
# if settings.get('spec_file'):
#     spec_file_button.configure(fg_color='green', hover_color='dark green', state='disabled')

def shutdown():
    if obs:
        obs.disconnect()
    app.destroy()

app.protocol("WM_DELETE_WINDOW", shutdown)
app.after(100, connectobs)
app.mainloop()