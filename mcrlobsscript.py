import obspython as obs
import os
from pathlib import Path

def script_description():
    return "haiiiiiiii\nLeague, Seed, Week number and seed type update instantly \nCommentator pfp + name through bot \n@dinotnt on dc"

botFile = ''

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
        'botFile',
        'Discord Bot File Location',
        obs.OBS_TEXT_DEFAULT
    )
    obs.obs_properties_add_button(
        p,
        'runBot',
        'Run Discord Bot',
        runBot
    )

    return p

def runBot(props, prop):
    global botFile
    if os.path.isfile(botFile):
        os.startfile(botFile)
    else:
        raise FileNotFoundError('Set the location of the discord bot script, if you do not have it -> https://github.com/dinotnt-lab/MCRL-obs-controller/blob/main/LeagueOBSBot.py')
    return True

def edit_text(string, sourcename):
    source = obs.obs_get_source_by_name(sourcename)
    if not source:
        return
    d = obs.obs_data_create()
    obs.obs_data_set_string(d, "text", str(string))
    obs.obs_source_update(source, d)
    obs.obs_data_release(d)
    obs.obs_source_release(source)

def set_seed(s):
    scene_source = obs.obs_get_source_by_name("COMMENTATORS")
    scene = obs.obs_scene_from_source(scene_source)

    for name in ["SHIP", "VILLAGE", "DT", "RP", "BT"]:
        item = obs.obs_scene_find_source_recursive(scene, name)

        if item:
            obs.obs_sceneitem_set_visible(item, name == s)

    obs.obs_source_release(scene_source)

def script_update(settings):
    global botFile
    league = obs.obs_data_get_int(settings, "league_number")
    seed = obs.obs_data_get_int(settings, "seed_number")
    week = obs.obs_data_get_int(settings, "week_number")
    seedtype = obs.obs_data_get_string(settings, 'seed_type')
    botFile = obs.obs_data_get_string(settings, 'botFile')

    edit_text(f'League {league}', 'League')
    edit_text(f'Seed {seed}', 'Seed')
    edit_text(f'Week {week}', 'Week numer')
    update_lbs(week, league)
    set_seed(seedtype)

def update_lbs(week, league):
    for source in ['Big Leaderboard', 'MATCH WINNER', 'lb']:
        source = obs.obs_get_source_by_name(source)
        if not source:
            return
        d = obs.obs_data_create()
        obs.obs_data_set_string(d, "url", f'https://mscl.pages.dev/week/?week={week}&league={league}')
        obs.obs_source_update(source, d)
        obs.obs_data_release(d)
        obs.obs_source_release(source)
