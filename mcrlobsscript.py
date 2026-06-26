import obspython as obs
import requests
from PIL import Image, ImageDraw
from io import BytesIO
from pathlib import Path
import os

comm1nameo = ''
comm2nameo = ''
comm1name = ''
comm2name = ''
comm1id = ''
comm2id = ''
downloads = Path.home() / "Downloads"

def script_description():
    return "haiiiiiiii\nLeague, Seed, Week number, commentator name overrides and seed type update instantly \nCommentator pfp + discord name requires apply \n@dinotnt on dc"

def script_properties():
    p = obs.obs_properties_create()

    obs.obs_properties_add_int(
        p,
        "league_number",
        "League",
        1,
        7,
        1
    )
    obs.obs_properties_add_int(
        p,
        "seed_number",
        "Seed",
        1,
        10,
        1
    )
    obs.obs_properties_add_int(
        p,
        "week_number",
        "Week",
        1,
        999999,
        1
    )

    l = obs.obs_properties_add_list(
        p,
        'seed_type',
        'Seed Type',
        obs.OBS_COMBO_TYPE_LIST,
        obs.OBS_COMBO_FORMAT_STRING,
    )

    obs.obs_property_list_add_string(
        l,
        'BT',
        'BT'
    )
    obs.obs_property_list_add_string(
        l,
        'RP',
        'RP'
    )
    obs.obs_property_list_add_string(
        l,
        'SHIP',
        'SHIP'
    )
    obs.obs_property_list_add_string(
        l,
        'DT',
        'DT'
    )
    obs.obs_property_list_add_string(
        l,
        'VILLAGE',
        'VILLAGE'
    )


    obs.obs_properties_add_text(
        p,
        "com1_id",
        "Commentator 1 Discord ID",
        False
    )
    obs.obs_properties_add_text(
        p,
        "com2_id",
        "Commentator 2 Discord ID",
        False
    )

    obs.obs_properties_add_button(
        p,
        'get_dc',
        'get dc name/pic',
        getdc
    )
    obs.obs_properties_add_button(
        p,
        'clear_coms',
        'clear commentators',
        clearcoms
    )

    obs.obs_properties_add_text(
        p,
        "com1_nameo",
        "Commentator 1 Name Override",
        False
    )
    obs.obs_properties_add_text(
        p,
        "com2_nameo",
        "Commentator 2 Name Override",
        False
    )

    return p

def clearcoms(x, y):
    edit_img('', 'commimg1')
    edit_img('', 'commimg2')
    edit_text('', 'comm1')
    edit_text('', 'comm2')

def edit_img(path, sourcename):
    source = obs.obs_get_source_by_name(sourcename)
    if not source:
        return
    d = obs.obs_data_create()
    obs.obs_data_set_string(d, "file", str(path))
    obs.obs_source_update(source, d)
    obs.obs_data_release(d)
    obs.obs_source_release(source)

def getdc(x, y):
    print('googogog')
    global comm1id, comm2id, comm1name, comm2name
    if comm1id:
        print('going')
        resp = requests.get('https://avatar-cyan.vercel.app/api/' + comm1id)
        if resp.status_code == 200:
            comm1name = resp.json()['username']
            if not os.path.isfile(downloads / f'{comm1name}.png'):
                file = getpfp(resp.json()['avatarUrl'], comm1name)
            else:
                file = downloads / f'{comm1name}.png'
            refreshcomname()
            edit_img(file, 'commimg1')
    if comm2id:
        print('going')
        resp = requests.get('https://avatar-cyan.vercel.app/api/' + comm2id)
        if resp.status_code == 200:
            comm2name = resp.json()['username']
            if not os.path.isfile(downloads / f'{comm2name}.png'):
                file = getpfp(resp.json()['avatarUrl'], comm2name)
            else:
                file = downloads / f'{comm2name}.png'            
            refreshcomname()
            edit_img(file, 'commimg2')
            
def edit_text(string, sourcename):
    source = obs.obs_get_source_by_name(sourcename)
    if not source:
        return
    d = obs.obs_data_create()
    obs.obs_data_set_string(d, "text", str(string))
    obs.obs_source_update(source, d)
    obs.obs_data_release(d)
    obs.obs_source_release(source)

def refreshcomname():
    global comm1name, comm2name, comm1nameo, comm2nameo
    if comm1nameo:
        edit_text(comm1nameo, 'comm1')
    else:
        edit_text(comm1name, 'comm1')
    if comm2nameo:
        edit_text(comm2nameo, 'comm2')
    else:
        edit_text(comm2name, 'comm2')

def set_seed(s):
    scene_source = obs.obs_get_source_by_name("COMMENTATORS")
    scene = obs.obs_scene_from_source(scene_source)

    for name in ["SHIP", "VILLAGE", "DT", "RP", "BT"]:
        item = obs.obs_scene_find_source_recursive(scene, name)

        if item:
            obs.obs_sceneitem_set_visible(item, name == s)

    obs.obs_source_release(scene_source)

def script_update(settings):
    global comm1id, comm2id, comm1name, comm2name, comm1nameo, comm2nameo
    league = obs.obs_data_get_int(settings, "league_number")
    seed = obs.obs_data_get_int(settings, "seed_number")
    week = obs.obs_data_get_int(settings, "week_number")
    seedtype = obs.obs_data_get_string(settings, 'seed_type')
    comm1id = obs.obs_data_get_string(settings, "com1_id")
    comm2id = obs.obs_data_get_string(settings, "com2_id")
    comm1nameo = obs.obs_data_get_string(settings, "com1_nameo")
    comm2nameo = obs.obs_data_get_string(settings, "com2_nameo")

    refreshcomname()
    edit_text(f'League {league}', 'League')
    edit_text(f'Seed {seed}', 'Seed')
    edit_text(f'Week {week}', 'Week numer')
    update_lbs(week, league)
    set_seed(seedtype)

def update_lbs(week, league):
    source = obs.obs_get_source_by_name('Big Leaderboard')
    if not source:
        return
    d = obs.obs_data_create()
    obs.obs_data_set_string(d, "url", f'https://mscl.pages.dev/week/?week={week}&league={league}')
    obs.obs_source_update(source, d)
    obs.obs_data_release(d)
    obs.obs_source_release(source)
    source = obs.obs_get_source_by_name('MATCH WINNER')
    if not source:
        return
    d = obs.obs_data_create()
    obs.obs_data_set_string(d, "url", f'https://mscl.pages.dev/week/?week={week}&league={league}')
    obs.obs_source_update(source, d)
    obs.obs_data_release(d)
    obs.obs_source_release(source)

def getpfp(url, name):
    global downloads
    resp = requests.get(url)
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

    filepath = downloads / f"{name}.png"

    result.save(filepath)

    return str(filepath)