from calendar import week
import json
import re
import threading
from io import BytesIO
from pathlib import Path
import CTkMessagebox
import customtkinter as ctk
import obsws_python
import requests
from PIL import Image, ImageDraw
from tkinter import filedialog

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

ROOT_DIR = Path(__file__).resolve().parent
DOWNLOADS_DIR = Path.home() / "downloads"
SETTINGS_PATH = ROOT_DIR / "settings.json"

try:
    with SETTINGS_PATH.open("r", encoding="utf-8") as handle:
        settings = json.load(handle)
except FileNotFoundError:
    settings = {}

app = ctk.CTk()
app.geometry("1000x640")
app.title("MCRL OBS Tool")
app.after(100, lambda: app.wm_attributes("-alpha", 0.99))
app.after(150, lambda: app.wm_attributes("-alpha", 1.0))

UPDATE_INTERVAL_MS = 2000

streamingplayerlist = []
obs = None
setup_complete = False
selectedstream = None
selectedspot = None
selectedspotelement = None
split_updating = False
poll_generation = 0
said_started = False
shown = {}
done = []
uuid_to_streamer = {}
players_in_room = []
info_lines = ["", "", "", "", ""]
show_heads = False

ACHIEVEMENT_ORDER = {
    "Killed Dragon": 0,
    "Enter End": 1,
    "Eye Spy": 2,
    "Blind": 3,
    "First Rod": 4,
    "Fortress": 5,
    "War Pigs": 6,
    "Bastion": 7,
    "Nether": 8,
    "Hot Stuff": 9,
    "Iron Pickaxe": 10,
    "Iron": 11,
}

ACHIEVEMENT_MAP = {
    "projectelo.timeline.dragon_death": "Killed Dragon",
    "story.enter_the_end": "Enter End",
    "story.follow_ender_eye": "Eye Spy",
    "projectelo.timeline.blind_travel": "Blind",
    "nether.obtain_blaze_rod": "First Rod",
    "nether.find_fortress": "Fortress",
    "nether.loot_bastion": "War Pigs",
    "nether.find_bastion": "Bastion",
    "story.enter_the_nether": "Nether",
    "story.lava_bucket": "Hot Stuff",
    "story.iron_tools": "Iron Pickaxe",
    "story.smelt_iron": "Iron",
}


def save_settings():
    with SETTINGS_PATH.open("w", encoding="utf-8") as handle:
        json.dump(settings, handle)


def validate_league(value):
    if value == "":
        return True
    return value.isdigit() and 1 <= int(value) <= 7


def validate_number(value):
    return value == "" or value.isdigit()


validate_league_cmd = app.register(validate_league)
validate_number_cmd = app.register(validate_number)


def set_info_text(message):
    if "info_label" in globals():
        info_label.configure(text=message)


def safe_obs_set(source, payload):
    if obs is None:
        return False
    try:
        obs.set_input_settings(source, payload, True)
        return True
    except Exception as exc:
        if "update_status_label" in globals():
            if 'No Source was found by the name' in str(exc):
                update_status_label.configure(text=f"OBS error: Check scene collection and element names are correct")
            update_status_label.configure(text=f"OBS error: {exc}")
        return False


def run_thread(function):
    threading.Thread(target=function, daemon=True).start()


def get_player_avatar(player):
    global show_heads

    if not show_heads:
        player["avatar_image"] = None
        return None

    avatar = player.get("avatar_image")
    if avatar is not None:
        return avatar

    try:
        response = requests.get(
            f"https://nmsr.nickac.dev/face/{player['ign']}",
            timeout=1,
        )
        response.raise_for_status()

        img = Image.open(BytesIO(response.content)).convert("RGBA").resize(
            (48, 48),
            Image.Resampling.LANCZOS,
        )
        avatar = ctk.CTkImage(img)
        player["avatar_image"] = avatar
        return avatar
    except Exception:
        player["avatar_image"] = None
        return None


def set_view_button_display(button, player):
    if button is None:
        return

    if player is None:
        button.configure(text="", image=None, compound="top")
        return

    button.configure(
        text=player.get("ign", ""),
        image=player.get("avatar_image"),
        compound="top",
    )


def loadplayerfile():
    global streamingplayerlist

    try:
        playerlist_path = filedialog.askopenfilename(
            title="Select .ranked file",
            filetypes=[("Ranked files", "*.ranked")],
        )
        if not playerlist_path:
            return

        with open(playerlist_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)

        filename = Path(playerlist_path).name
        match = re.match(r"mcrl_(\d+)_(\d+)\.ranked$", filename)
        if not match:
            file_status_label.configure(text="Invalid ranked filename format")
            return

        league = match.group(1)
        week = match.group(2)

        league_entry.set(league)
        week_entry.set(week)

        for widget in streams_frame.winfo_children():
            widget.destroy()

        streamingplayerlist.clear()

        for player in data:
            username = str(player.get("twitch_username") or "").strip()
            if not username:
                continue

            twitch_name = None
            if "http://" in username or "https://" in username or "twitch.tv" in username:
                url_match = re.match(
                    r"^(?:https?://)?(?:www\.)?twitch\.tv/([A-Za-z0-9_]+)/?$",
                    username,
                )
                if url_match:
                    twitch_name = url_match.group(1)
            else:
                twitch_name = username

            if not twitch_name:
                continue

            streamingplayerlist.append(
                {
                    "ign": player.get("ign") or player.get("display_name") or twitch_name,
                    "twitch": twitch_name,
                    "displayname": player.get("display_name") or twitch_name,
                    "uuid": None,
                    "achievement": "",
                    "element": None,
                    "frame": None,
                    "avatar_image": None,
                }
            )

        for index, player in enumerate(streamingplayerlist, start=1):
            player_frame = ctk.CTkFrame(streams_frame, corner_radius=10)
            player_frame.pack(padx=5, pady=2, fill="x")

            avatar = get_player_avatar(player)

            element = ctk.CTkButton(
                player_frame,
                text=f"{player['ign']}\n",
                image=avatar,
                width=220,
                height=38,
                command=lambda p=player: selectstream(p),
            )
            element.pack(padx=5, pady=3, fill="x")

            player["element"] = element
            player["frame"] = player_frame

            file_status_label.configure(text=f"{index}/{len(streamingplayerlist)} streamers loaded")
            app.update()

        file_status_label.configure(text=f"Loaded {len(streamingplayerlist)} streamers")
        playerlistbutton.configure(fg_color="green", hover_color="dark green")
        updateobs()
    except Exception as exc:
        file_status_label.configure(text=str(exc))


def connectobs():
    global obs

    try:
        obs = obsws_python.ReqClient(
            host="localhost",
            port=4455,
            password=obs_password_entry.get(),
            timeout=3,
        )
        obs_status.configure(text="Success")
        obs_button.configure(fg_color="green", hover_color="dark green", state="disabled")
    except ConnectionRefusedError:
        obs = None
        obs_status.configure(
            text="OBS websockets not enabled or port changed (return to default). Tools > Websocket Server Settings"
        )
    except Exception as exc:
        obs = None
        error = str(exc).lower()
        if "password" in error or "failed" in error:
            obs_status.configure(text="Incorrect or missing password")
        else:
            obs_status.configure(text=f"Error: {exc}")


def updateobs():
    global setup_complete

    if not streamingplayerlist:
        update_status_label.configure(text="Missing Player File")
        return
    if not bot_entry.get():
        update_status_label.configure(text="Missing Discord Bot Token")
        return
    if not api_entry.get():
        update_status_label.configure(text="Missing MCSR API Key")
        return
    if not ign_entry.get():
        update_status_label.configure(text="Missing MCSR ign")
        return
    if obs is None:
        update_status_label.configure(text="OBS not connected")
        return

    settings["obs_password"] = obs_password_entry.get()
    settings["ranked_api_key"] = api_entry.get()
    settings["discord_token"] = bot_entry.get()
    settings["ign"] = ign_entry.get()
    save_settings()

    safe_obs_set("League", {"text": f"League {league_entry.get()}", "font_size": 30})
    safe_obs_set("Week", {"text": f"Week {week_entry.get()}", "font_size": 30})
    safe_obs_set("Seed", {"text": f"Seed {seed_entry.get()}", "font_size": 30})

    for source in ["Big Leaderboard", "MATCH WINNER", "lb"]:
        safe_obs_set(
            source,
            {
                "url": f"https://mscl.pages.dev/week/?week={week_entry.get()}&league={league_entry.get()}"
            }
        )

    run_thread(commentators_thread)
    safe_obs_set("comm1", {"text": comm1_name_entry.get()})
    safe_obs_set("comm2", {"text": comm2_name_entry.get()})

    setup_complete = True
    update_button.configure(fg_color="green", hover_color="dark green")
    update_status_label.configure(text="OBS updated")


def discord_user_info(user_id):
    response = requests.get(
        f"https://discord.com/api/v10/users/{user_id}",
        headers={"Authorization": f"Bot {settings.get('discord_token', '')}"},
        timeout=5,
    )
    response.raise_for_status()
    return response.json()


def circlify(url, name):
    response = requests.get(url, timeout=10)
    response.raise_for_status()

    img = Image.open(BytesIO(response.content)).convert("RGBA")
    img = img.resize((256, 256))

    size = min(img.width, img.height)
    left = (img.width - size) // 2
    top = (img.height - size) // 2
    img = img.crop((left, top, left + size, top + size))

    mask_size = size * 4
    mask = Image.new("L", (mask_size, mask_size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, mask_size, mask_size), fill=255)
    mask = mask.resize((size, size), Image.Resampling.LANCZOS)

    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(img, (0, 0), mask)

    filepath = DOWNLOADS_DIR / f"{name}-commentator-pfp.png"
    result.save(filepath)
    return str(filepath)


def commentators_thread():
    global pcomm1, pcomm2

    try:
        comm1_id = comm1_entry.get().strip()
        comm2_id = comm2_entry.get().strip()

        if not comm1_id:
            safe_obs_set("commimg1", {"file": ""})
            app.after(0, lambda: comm1_name_entry.delete(0, "end"))
            pcomm1 = ""
        elif comm1_id != pcomm1:
            pcomm1 = comm1_id
            data = discord_user_info(comm1_id)
            name = data.get("global_name")
            avatar = data.get("avatar")
            filepath = ""
            if avatar:
                filepath = circlify(
                    f"https://cdn.discordapp.com/avatars/{comm1_id}/{avatar}.png?size=512",
                    name,
                )
            app.after(0, lambda: comm1_name_entry.delete(0, "end"))
            app.after(0, lambda: comm1_name_entry.insert(0, name))
            safe_obs_set("commimg1", {"file": filepath})

        if not comm2_id:
            safe_obs_set("commimg2", {"file": ""})
            app.after(0, lambda: comm2_name_entry.delete(0, "end"))
            pcomm2 = ""
        elif comm2_id != pcomm2:
            pcomm2 = comm2_id
            data = discord_user_info(comm2_id)
            name = data.get("global_name")
            avatar = data.get("avatar")
            filepath = ""
            if avatar:
                filepath = circlify(
                    f"https://cdn.discordapp.com/avatars/{comm2_id}/{avatar}.png?size=512",
                    name,
                )
            app.after(0, lambda: comm2_name_entry.delete(0, "end"))
            app.after(0, lambda: comm2_name_entry.insert(0, name))
            safe_obs_set("commimg2", {"file": filepath})
    except Exception as exc:
        app.after(0, lambda: update_status_label.configure(text=str(exc)))


def selectstream(player):
    global selectedstream

    if selectedstream != None:
        selectedstream["element"].configure(fg_color="#1f6aa5")

    if selectedstream == player:
        selectedstream = None
        return

    selectedstream = player
    player["element"].configure(fg_color="blue")


def find_streamer_by_twitch(channel):
    for streamer in streamingplayerlist:
        if streamer.get("twitch") == channel:
            return streamer
    return None


def get_obs_url(spot):
    try:
        response = obs.get_input_settings(spot)
        return response.input_settings.get("url", "")
    except Exception:
        return ""


def get_obs_name(spot):
    try:
        response = obs.get_input_settings(f"pov{spot}name")
        return response.input_settings.get("text", "")
    except Exception:
        return ""


def selectspot(spot, element):
    global selectedstream, selectedspot, selectedspotelement

    if selectedstream is not None:
        channel = selectedstream["twitch"]
        url = (
            f"https://player.twitch.tv/?channel={channel}"
            "&enableExtensions=true&muted=false&parent=twitch.tv"
            "&player=popout&quality=chunked&volume=0"
        )
        safe_obs_set(f"pov{spot}", {"url": url})
        safe_obs_set(f"pov{spot}name", {"text": selectedstream["displayname"]})
        safe_obs_set(f"headpov{spot}", {"url": f'https://nmsr.nickac.dev/face/{selectedstream["ign"]}'})

        set_view_button_display(element, selectedstream)
        element.configure(fg_color="#1f6aa5")
        selectedstream["element"].configure(fg_color="#1f6aa5")
        selectedstream = None
        return

    if selectedspot is not None:
        aurl = get_obs_url('pov' + str(selectedspot))
        aname = get_obs_name(selectedspot)
        ahead = get_obs_url(f"headpov{selectedspot}")
        burl = get_obs_url('pov' + str(spot))
        bname = get_obs_name(spot)
        bhead = get_obs_url(f"headpov{spot}")

        safe_obs_set(f"pov{spot}", {"url": aurl})
        safe_obs_set(f"pov{spot}name", {"text": aname})
        safe_obs_set(f"headpov{spot}", {"url": ahead})

        safe_obs_set(f"pov{selectedspot}", {"url": burl})
        safe_obs_set(f"pov{selectedspot}name", {"text": bname})
        safe_obs_set(f"headpov{selectedspot}", {"url": bhead})

        a_channel = aurl.replace(
            "https://player.twitch.tv/?channel=", ""
        ).replace(
            "&enableExtensions=true&muted=false&parent=twitch.tv&player=popout&quality=chunked&volume=0",
            "",
        )
        b_channel = burl.replace(
            "https://player.twitch.tv/?channel=", ""
        ).replace(
            "&enableExtensions=true&muted=false&parent=twitch.tv&player=popout&quality=chunked&volume=0",
            "",
        )

        a_player = find_streamer_by_twitch(a_channel)
        b_player = find_streamer_by_twitch(b_channel)

        set_view_button_display(element, a_player)
        set_view_button_display(selectedspotelement, b_player)
        selectedspotelement.configure(fg_color="#1f6aa5")
        selectedspotelement = None
        selectedspot = None
        return

    element.configure(fg_color="blue")
    selectedspot = spot
    selectedspotelement = element


def clear():
    global selectedspot, selectedspotelement

    if selectedspot is None:
        return

    safe_obs_set(f"pov{selectedspot}", {"url": ""})
    safe_obs_set(f"pov{selectedspot}name", {"text": ""})
    safe_obs_set(f"headpov{selectedspot}", {"url": ""})

    if selectedspot == 1:
        button = view_1_button
    elif selectedspot == 2:
        button = view_2_button
    elif selectedspot == 3:
        button = view_3_button
    elif selectedspot == 4:
        button = view_4_button
    else:
        button = None

    if button is not None:
        set_view_button_display(button, None)
        button.configure(fg_color="#1f6aa5")

    selectedspot = None
    selectedspotelement = None


def reorder_streamer_buttons():
    sorted_players = sorted(
        streamingplayerlist,
        key=lambda player: (
            ACHIEVEMENT_ORDER.get(player.get("achievement"), len(ACHIEVEMENT_ORDER)),
            player.get("ign", "").lower(),
        ),
    )

    for player in sorted_players:
        player["frame"].pack_forget()

    for player in sorted_players:
        player["frame"].pack(padx=5, pady=2, fill="x")


def update_splits_display(data):
    global info_lines, players_in_room, uuid_to_streamer, shown, done, said_started

    if data.get("status") == "error":
        CTkMessagebox.CTkMessagebox(
            title="Alert",
            message=data.get("data", {}).get("error", "Unknown API error"),
            icon="warning",
        )
        return

    payload = data.get("data", {})
    players_in_room = payload.get("players", [])
    status = payload.get("status")

    if status == "counting" and "Match Countdown Started" not in info_lines:
        info_lines = info_lines[1:] + ["Match Countdown Started"]
    elif status == "generate" and "Match Generation Started" not in info_lines:
        info_lines = info_lines[1:] + ["Match Generation Started"]
    elif status == "running" and "Match Started" not in info_lines and not said_started:
        info_lines = info_lines[1:] + ["Match Started"]
        said_started = True
        done.clear()
        shown.clear()
    elif status == "idle":
        done.clear()
        shown.clear()
        info_lines = ["", "", "", "", ""]
        said_started = False
        live_by_name = {player["nickname"]: player for player in players_in_room}
        uuid_to_streamer.clear()

        for streamer in streamingplayerlist:
            live = live_by_name.get(streamer["ign"])
            if live is None:
                streamer["achievement"] = ""
                streamer["uuid"] = None
                streamer["element"].configure(text=f"{streamer['ign']}\nNot In Room")
            else:
                streamer["uuid"] = live.get("uuid")
                streamer["achievement"] = ""
                uuid_to_streamer[live["uuid"]] = streamer
                streamer["element"].configure(text=f"{streamer['ign']}\nIn Room")
    elif status == "running":
        if not uuid_to_streamer:
            live_by_name = {player["nickname"]: player for player in players_in_room}
            for streamer in streamingplayerlist:
                live = live_by_name.get(streamer["ign"])
                if live is None:
                    streamer["achievement"] = ""
                    streamer["uuid"] = None
                    streamer["element"].configure(text=f"{streamer['ign']}\nNot In Room")
                else:
                    streamer["uuid"] = live.get("uuid")
                    streamer["achievement"] = ""
                    uuid_to_streamer[live["uuid"]] = streamer
                    streamer["element"].configure(text=f"{streamer['ign']}\nIn Room")

        for timeline in payload.get("timelines", []):
            streamer = uuid_to_streamer.get(timeline.get("uuid"))
            if streamer is None:
                continue

            ign = streamer.get("ign")
            previous = shown.get(ign)
            if previous is None or timeline.get("time") > previous.get("time"):
                achievement = ACHIEVEMENT_MAP.get(timeline.get("type"))
                if achievement:
                    shown[ign] = timeline
                    if streamer.get("achievement") != achievement:
                        streamer["achievement"] = achievement
                        streamer["element"].configure(text=f"{ign}\n{achievement}")
                        reorder_streamer_buttons()
                    if achievement not in done:
                        done.append(achievement)
                        info_lines = info_lines[1:] + [f"{achievement} by {streamer['ign']}"]

        for completion in payload.get("completions", []):
            streamer = uuid_to_streamer.get(completion.get("uuid"))
            if streamer and streamer.get("frame") is not None:
                streamer["frame"].pack_forget()
                streamer["element"].configure(text=f"{streamer['ign']}\nCompleted")

    info_label.configure(text="\n".join(info_lines))


def fetch_splits():
    global poll_generation

    if not split_updating:
        return

    generation = poll_generation
    try:
        response = requests.get(
            "https://api.mcsrranked.com/users/" + settings.get("ign") + "/live",
            headers={"Private-Key": settings.get("ranked_api_key")},
            timeout=5,
        )
        response.raise_for_status()
        data = response.json()
        app.after(0, lambda: update_splits_display(data))
    except requests.HTTPError as exc:
        app.after(0, lambda response=response: info_label.configure(text="\n".join(info_lines[1:] + [response.json().get('data').get('error')])))
    except Exception as exc:
        app.after(0, lambda exc=exc: info_label.configure(text="\n".join(info_lines[1:] + [str(exc)])))
    finally:
        if split_updating and generation == poll_generation:
            app.after(UPDATE_INTERVAL_MS, fetch_splits)


def start_live_polling():
    global split_updating, poll_generation

    if split_updating:
        return

    split_updating = True
    poll_generation += 1
    run_thread(fetch_splits)


def stop_live_polling():
    global split_updating
    split_updating = False


def tab_changed():
    if tabs.get() == "Streams":
        if not setup_complete:
            tabs.set("Setup")
            CTkMessagebox.CTkMessagebox(
                title="Incomplete Setup",
                message="Complete setup before continuing",
                icon="warning",
            )
            return
        start_live_polling()
    else:
        stop_live_polling()


def set_show_heads():
    global show_heads

    show_heads = bool(show_heads_switch.get())
    settings["heads"] = show_heads
    save_settings()

    for player in streamingplayerlist:
        if player.get("element") is None:
            continue

        if show_heads:
            avatar = get_player_avatar(player)
            player["element"].configure(image=avatar)
        else:
            player["avatar_image"] = None
            player["element"].configure(image=None)


tabs = ctk.CTkTabview(app, command=tab_changed)
tabs.pack(expand=True, fill="both", padx=15, pady=6)
setup_tab = tabs.add("Setup")
advanced_tab = tabs.add("Advanced Settings")
streams_tab = tabs.add("Streams")

d# region Setup tab
file_frame = ctk.CTkFrame(setup_tab)
file_frame.pack(fill="x", padx=20, pady=2)
file_label = ctk.CTkLabel(file_frame, text="Player File:")
file_label.pack(side="left", padx=10, pady=2)
playerlistbutton = ctk.CTkButton(file_frame, text="Open Player File", command=loadplayerfile)
playerlistbutton.pack(side="right", padx=10, pady=2)
file_status_label = ctk.CTkLabel(file_frame, text="", text_color="gray")
file_status_label.pack(side="right", padx=10, pady=2)

obs_frame = ctk.CTkFrame(setup_tab)
obs_frame.pack(fill="x", padx=20, pady=2)
obs_label = ctk.CTkLabel(obs_frame, text="Connect OBS:")
obs_label.pack(side="left", padx=10, pady=2)
obs_button = ctk.CTkButton(obs_frame, text="Connect to OBS", command=connectobs)
obs_button.pack(side="right", padx=10, pady=2)
obs_status = ctk.CTkLabel(obs_frame, text="", text_color="gray")
obs_status.pack(side="right", padx=10, pady=2)

obs_password_frame = ctk.CTkFrame(setup_tab)
obs_password_frame.pack(fill="x", padx=20, pady=2)
obs_password_label = ctk.CTkLabel(obs_password_frame, text="OBS password:")
obs_password_label.pack(side="left", padx=10, pady=2)
obs_password_entry = ctk.CTkEntry(obs_password_frame)
obs_password_entry.pack(side="right", padx=10, pady=2)

league_frame = ctk.CTkFrame(setup_tab)
league_frame.pack(fill="x", padx=20, pady=2)
league_label = ctk.CTkLabel(league_frame, text="League #: (1-7)")
league_label.pack(side="left", padx=10, pady=2)
league_entry = ctk.CTkEntry(league_frame, validate="key", validatecommand=(validate_league_cmd, "%P"))
league_entry.pack(side="right", padx=10, pady=2)

week_frame = ctk.CTkFrame(setup_tab)
week_frame.pack(fill="x", padx=20, pady=2)
week_label = ctk.CTkLabel(week_frame, text="Week #:")
week_label.pack(side="left", padx=10, pady=2)
week_entry = ctk.CTkEntry(week_frame, validate="key", validatecommand=(validate_number_cmd, "%P"))
week_entry.pack(side="right", padx=10, pady=2)

seed_frame = ctk.CTkFrame(setup_tab)
seed_frame.pack(fill="x", padx=20, pady=2)
seed_label = ctk.CTkLabel(seed_frame, text="Seed #:")
seed_label.pack(side="left", padx=10, pady=2)
seed_entry = ctk.CTkEntry(seed_frame, validate="key", validatecommand=(validate_number_cmd, "%P"))
seed_entry.pack(side="right", padx=10, pady=2)

comm1_frame = ctk.CTkFrame(setup_tab)
comm1_frame.pack(fill="x", padx=20, pady=2)
comm1_label = ctk.CTkLabel(comm1_frame, text="Commentator 1's discord ID:")
comm1_label.pack(side="left", padx=10, pady=2)
comm1_entry = ctk.CTkEntry(comm1_frame, validate="key", validatecommand=(validate_number_cmd, "%P"))
comm1_entry.pack(side="right", padx=10, pady=2)

comm2_frame = ctk.CTkFrame(setup_tab)
comm2_frame.pack(fill="x", padx=20, pady=2)
comm2_label = ctk.CTkLabel(comm2_frame, text="Commentator 2's discord ID:")
comm2_label.pack(side="left", padx=10, pady=2)
comm2_entry = ctk.CTkEntry(comm2_frame, validate="key", validatecommand=(validate_number_cmd, "%P"))
comm2_entry.pack(side="right", padx=10, pady=2)

comm1_name_frame = ctk.CTkFrame(setup_tab)
comm1_name_frame.pack(fill="x", padx=20, pady=2)
comm1_name_label = ctk.CTkLabel(comm1_name_frame, text="Commentator 1's name:")
comm1_name_label.pack(side="left", padx=10, pady=2)
comm1_name_entry = ctk.CTkEntry(comm1_name_frame)
comm1_name_entry.pack(side="right", padx=10, pady=2)

comm2_name_frame = ctk.CTkFrame(setup_tab)
comm2_name_frame.pack(fill="x", padx=20, pady=2)
comm2_name_label = ctk.CTkLabel(comm2_name_frame, text="Commentator 2's name:")
comm2_name_label.pack(side="left", padx=10, pady=2)
comm2_name_entry = ctk.CTkEntry(comm2_name_frame)
comm2_name_entry.pack(side="right", padx=10, pady=2)

api_frame = ctk.CTkFrame(setup_tab)
api_frame.pack(fill="x", padx=20, pady=2)
api_label = ctk.CTkLabel(api_frame, text="MCSR Ranked API key: (profile > settings)")
api_label.pack(side="left", padx=10, pady=2)
api_entry = ctk.CTkEntry(api_frame)
api_entry.pack(side="right", padx=10, pady=2)

ign_frame = ctk.CTkFrame(setup_tab)
ign_frame.pack(fill="x", padx=20, pady=2)
ign_label = ctk.CTkLabel(ign_frame, text="Your MCSR ign: ")
ign_label.pack(side="left", padx=10, pady=2)
ign_entry = ctk.CTkEntry(ign_frame)
ign_entry.pack(side="right", padx=10, pady=2)

bot_frame = ctk.CTkFrame(setup_tab)
bot_frame.pack(fill="x", padx=20, pady=2)
bot_label = ctk.CTkLabel(bot_frame, text="Discord bot key:")
bot_label.pack(side="left", padx=10, pady=2)
bot_entry = ctk.CTkEntry(bot_frame)
bot_entry.pack(side="right", padx=10, pady=2)

update_frame = ctk.CTkFrame(setup_tab)
update_frame.pack(fill="x", padx=20, pady=2)
update_label = ctk.CTkLabel(update_frame, text="Update OBS")
update_label.pack(side="left", padx=10, pady=2)
update_button = ctk.CTkButton(update_frame, text="Update", command=updateobs)
update_button.pack(side="right", padx=10, pady=2)
update_status_label = ctk.CTkLabel(update_frame, text="", text_color="gray")
update_status_label.pack(side="right", padx=10, pady=2)
# endregion

# region Advanced Settings Tab

show_head_frame = ctk.CTkFrame(advanced_tab)
show_head_frame.pack(fill="x", padx=20, pady=2)
show_heads_label = ctk.CTkLabel(show_head_frame, text="Show Heads in app: (will impact performance)")
show_heads_label.pack(side="left", padx=10, pady=2)
show_heads_switch = ctk.CTkSwitch(show_head_frame, command=set_show_heads, text='')
show_heads_switch.pack(side="right", padx=10, pady=2)
show_heads_switch.deselect()

# endregion

# region Streams tab
streams_frame = ctk.CTkScrollableFrame(streams_tab, width=260, height=520)
streams_frame.pack(padx=20, pady=5, side="left", anchor="n", fill="y")

info_obs_frame = ctk.CTkFrame(streams_tab)
info_obs_frame.pack(padx=20, pady=5, side="right", anchor="n", fill="both", expand=True)

info_frame = ctk.CTkFrame(info_obs_frame)
info_frame.pack(fill="x", padx=20, pady=5)
info_title = ctk.CTkLabel(info_frame, text="Match Info", font=ctk.CTkFont(size=20))
info_title.pack(fill="x", padx=5, pady=5)
info_label = ctk.CTkLabel(info_frame, text="\n\n\n\n\n")
info_label.pack(fill="x", padx=5, pady=5)

obs_input_frame = ctk.CTkFrame(info_obs_frame)
obs_input_frame.pack(fill="x", padx=20, pady=5)
obs_input_title = ctk.CTkLabel(obs_input_frame, text="OBS Control", font=ctk.CTkFont(size=20))
obs_input_title.pack(fill="x", padx=5, pady=5)

view_1_button = ctk.CTkButton(obs_input_frame, width=150, height=100, text="", command=lambda: selectspot(1, view_1_button))
view_1_button.pack(side="left", padx=10, pady=10)

right_view_frame = ctk.CTkFrame(obs_input_frame)
right_view_frame.pack(side="right", padx=10, pady=10)
view_2_button = ctk.CTkButton(right_view_frame, width=100, height=40, text="", command=lambda: selectspot(2, view_2_button))
view_2_button.pack(pady=5)
view_3_button = ctk.CTkButton(right_view_frame, width=100, height=40, text="", command=lambda: selectspot(3, view_3_button))
view_3_button.pack(pady=5)
view_4_button = ctk.CTkButton(right_view_frame, width=100, height=40, text="", command=lambda: selectspot(4, view_4_button))
view_4_button.pack(pady=5)

clear_button = ctk.CTkButton(info_obs_frame, text="Clear Selected", command=clear)
clear_button.pack()

# endregion

seed_entry.set(1)
if settings.get("obs_password"):
    obs_password_entry.set(str(settings.get("obs_password")))
if settings.get("ranked_api_key"):
    api_entry.set(str(settings.get("ranked_api_key")))
if settings.get("discord_token"):
    bot_entry.set(str(settings.get("discord_token")))
if settings.get("ign"):
    ign_entry.set(str(settings.get("ign")))
show_heads = bool(settings.get("heads", False))
show_heads_switch.set(show_heads)

def shutdown():
    global obs
    if obs is not None:
        try:
            obs.disconnect()
        except Exception:
            pass
    app.destroy()

app.protocol("WM_DELETE_WINDOW", shutdown)
app.after(100, connectobs)
app.mainloop()


## Todo
# - chat -> inv button
# - set names of elements so obs doesnt have to be right
# - set settings location to appdata
# - seeds