import discord
from discord import app_commands
import obsws_python
import os
import requests
from PIL import Image, ImageDraw
from io import BytesIO
from pathlib import Path

intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

commentators = {}
current_thread = None
obs = None
downloads = Path.home() / "Downloads"
dir_path = os.path.dirname(os.path.realpath(__file__))
token_file = os.path.join(dir_path, "LeagueOBSBotToken.txt")

GUILD_ID = discord.Object(id=1511365088718880788) # mcrl organisation server

def circlify(url, name):
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

    filepath = downloads / f"{name}-commentator-pfp.png"

    result.save(filepath)

    return str(filepath)

def update_commentators(commentators):
    obs.set_input_settings('comm1', {'text': commentators['comm1']['name']}, True)

    if not os.path.isfile(downloads / f"{commentators['comm1']['name']}-commentator-pfp.png"):
        file = circlify(commentators['comm1']['pfp'], commentators['comm1']['name'])
    else:
        file = downloads / f"{commentators['comm1']['name']}-commentator-pfp.png"

    obs.set_input_settings('commimg1', {'file': str(file)}, True)

    if commentators['comm2'] is not None:
        obs.set_input_settings('comm2', {'text': commentators['comm2']['name']}, True)
        if not os.path.isfile(downloads / f"{commentators['comm2']['name']}-commentator-pfp.png"):
            file = circlify(commentators['comm2']['pfp'], commentators['comm2']['name'])
        else:
            file = downloads / f"{commentators['comm2']['name']}-commentator-pfp.png"
    
        obs.set_input_settings('commimg2', {'file': str(file)}, True)
    else:
        obs.set_input_settings('comm2', {'text': ''}, True)
        obs.set_input_settings('commimg2', {'file': ''}, True)

@tree.command(name="set-name-overrides", description="Set commentators name overrides", guild=GUILD_ID)
@app_commands.describe(comm1="First commentator name (optional)", comm2="Second commentator (optional)")
async def set_commentators(interaction: discord.Interaction, comm1: str | None, comm2: str | None):
    global commentators
    if comm1:
        old = commentators['comm1']['name']
        commentators['comm1']['name'] = comm1    
        await interaction.response.send_message(f'Updated {old} to {comm1}')

    elif comm2:
        if commentators['comm2'] is not None:
            old = commentators['comm2']['name']
            commentators['comm2']['name'] = comm2
            await interaction.response.send_message(f'Updated {old} to {comm2}')
        else:
            await interaction.response.send_message('No second commentator set')
    update_commentators(commentators)

@tree.command(name="set-commentators", description="Set commentators", guild=GUILD_ID)
@app_commands.describe(comm1="First commentator", comm2="Second commentator (optional)")
async def set_commentators(interaction: discord.Interaction, comm1: discord.Member, comm2: discord.Member | None):
    global commentators, obs
    commentators["comm1"] = {"id": comm1.id, "name": comm1.display_name, "pfp": str(comm1.display_avatar.url)}

    commentators["comm2"] = None
    if comm2 is not None:
        commentators["comm2"] = {"id": comm2.id, "name": comm2.display_name, "pfp": str(comm2.display_avatar.url)}
    update_commentators(commentators)
    if comm2:
        await interaction.response.send_message(f"Commentators updated to {commentators['comm1']['name']} and {commentators['comm2']['name']} \n /set-name-override to change name from default")
    else:
        await interaction.response.send_message(f"Commentator updated to {commentators['comm1']['name']} \n /set-name-override to change name from default")
    
@tree.command(name="obs-connect", description="Connect to OBS", guild=GUILD_ID)
@app_commands.describe(password="OBS WebSocket password")
async def obs_connect(interaction: discord.Interaction, password: str | None = None):
    global obs

    await interaction.response.defer(thinking=True)

    if obs is not None:
        await interaction.followup.send("Already connected to OBS")
        return
    try:
        obs = obsws_python.ReqClient(host="localhost", port=4455, password=password, timeout=5)

    except ConnectionRefusedError:
        await interaction.followup.send('OBS websockets not enabled or port changed (return to default). Tools > Websocket Server Settings')
        return
    
    except Exception as e:
        obs = None
        error = str(e).lower()

        if "password" in error:
            await interaction.followup.send("Incorrect or missing password")
        elif "failed" in error:
            await interaction.followup.send("Incorrect or missing password")
        else:
            await interaction.followup.send(f'Error: `{e}`')
        return

    await interaction.followup.send("Successfully connected to OBS, now /set-commentators or /set-name-overrides")
    os.system('cls')
    print('Successfully connected to OBS')
    print('Use /set-commentators or /set-name-overrides in #streamBot')
    print('Happy Streaming :)')

@bot.event
async def on_ready():
    global current_thread, streamer, obs, token
    try:
        guild = GUILD_ID
        synced = await tree.sync(guild=guild)
        print(f'synced {len(synced)} commands to guild {guild.id}')
    except Exception as e:
        print(f'Error syncing: {e}')

    print(f"Logged into {bot.user}")
    with open(dir_path + '/LeagueOBSBotToken.txt', 'w') as f:
        f.write(token)
    print('_'*100)
    print()

    try:
        print('Attempting autoconnection to obs')
        obs = obsws_python.ReqClient(host="localhost", port=4455, timeout=5)
        os.system('cls')
        print('Successfully connected to OBS')
        print('Use /set-commentators or /set-name-overrides in #streamBot')
        print('Happy Streaming :)')
        
    except:
        os.system('cls')
        print('Could not automatically connect to obs, please run /obs-connect to fix in #streamBot')

while True:
    if os.path.isfile(token_file):
        with open(token_file, "r") as f:
            token = f.read().strip()
    else:
        os.system("cls")
        print("You do not have a token set up. Check discord for it")
        token = input("Token >> ").strip()

    try:
        bot.run(token)
        break
    except discord.errors.LoginFailure:
        print("Improper token.")
        if os.path.isfile(token_file):
            os.remove(token_file)
        input("Relaunch script, press enter to close")
        break
    except Exception as e:
        print(e)
        break