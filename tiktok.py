from tiktokapipy.async_api import AsyncTikTokAPI
from playwright.async_api import async_playwright
import asyncio, nest_asyncio, threading
from uploader import uploadVideo
import ffmpeg
from discord_webhook import DiscordWebhook
import interactions
import time, datetime, schedule
import os, glob, traceback, warnings
import random
import dotenv

# Don't clog standard output with warnings
warnings.filterwarnings("ignore")
# Allow for the nesting of the Discord bot Async loop as well as the TikTok video Async loop
nest_asyncio.apply()

# Load .env variables
dotenv_file = dotenv.find_dotenv()
dotenv.load_dotenv(dotenv_file)

session_id = os.environ['SESSION-ID']
target_user = os.environ['TARGET-USER']
user_id = os.environ['USER-ID']
bot_token = os.environ['BOT-TOKEN']
webhook_url = os.environ['WEBHOOK-URL']
guild_id = int(os.environ['GUILD-ID'])
number = int(os.environ['NUMBER'])

# Helper class to allow for pretty output printing
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    ENDC = '\033[0m'
    FAIL = '\033[91m'

# Function for Playwright which blocks Google ads from being displayed on the website
# Without this, downloading the TikTok video would not work
# See https://www.scrapingbee.com/webscraping-questions/playwright/how-to-block-resources-in-playwright/
def route_intercept(route):
    if route.request.resource_type == "image":
        return route.abort()
    if "google" in route.request.url:
        return route.abort()
    return route.continue_()

# Function for handling the saving of the video
async def save_video(link):
    # Use playwright to navigate to the website (https://snaptik.app/) and download the video
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.route("**/*", route_intercept)
        await page.set_viewport_size({"width": 1920, "height": 1080})
        await page.goto("https://snaptik.app/")
        await page.wait_for_load_state('networkidle')
        input = await page.query_selector('#url')
        await input.type(link)
        await page.wait_for_selector('#hero > div > form > button')
        button1 = await page.query_selector('#hero > div > form > button')
        await button1.click()
        await page.wait_for_selector('#download > div > div.video-links > a:nth-child(1)')
        button2 = await page.query_selector('#download > div > div.video-links > a:nth-child(1)')
        async with page.expect_download() as download_info:
            await button2.click()
        download = await download_info.value
        await download.save_as("tiktok.mp4")
        await browser.close()

# Function for handling the compressing of the video to ensure it can be sent within Discord file size limit
# See https://stackoverflow.com/questions/64430805/how-to-compress-video-to-target-size-by-python
def compress_video(video_full_path, output_file_name, target_size):
    # Reference: https://en.wikipedia.org/wiki/Bit_rate#Encoding_bit_rate
    min_audio_bitrate = 32000
    max_audio_bitrate = 256000

    probe = ffmpeg.probe(video_full_path)
    # Video duration, in s.
    duration = float(probe['format']['duration'])
    # Audio bitrate, in bps.
    audio_bitrate = float(probe['streams'][0]['bit_rate'])
    # Target total bitrate, in bps.
    target_total_bitrate = (target_size * 1024 * 8) / (1.073741824 * duration)

    # Target audio bitrate, in bps
    if 10 * audio_bitrate > target_total_bitrate:
        audio_bitrate = target_total_bitrate / 10
        if audio_bitrate < min_audio_bitrate < target_total_bitrate:
            audio_bitrate = min_audio_bitrate
        elif audio_bitrate > max_audio_bitrate:
            audio_bitrate = max_audio_bitrate
    # Target video bitrate, in bps.
    video_bitrate = target_total_bitrate - audio_bitrate

    i = ffmpeg.input(video_full_path)
    ffmpeg.output(i, os.devnull,
                  **{'c:v': 'libx264', 'b:v': video_bitrate, 'pass': 1, 'f': 'mp4', 'loglevel': 'quiet'}
                  ).overwrite_output().run()
    ffmpeg.output(i, output_file_name,
                  **{'c:v': 'libx264', 'b:v': video_bitrate, 'pass': 2, 'c:a': 'aac', 'b:a': audio_bitrate, 'loglevel': 'quiet'}
                  ).overwrite_output().run()

# Function for handling the editing of the video
# Uses python-ffmpeg
def edit_video():
    print("Stacking videos...")
    # Get random video and edit to stack them on top of each other
    random_video = "pointing_clips/" + random.choice([x for x in os.listdir("pointing_clips") if ".mp4" in x])   
    targetStream = ffmpeg.input('tiktok.mp4')
    width = int(ffmpeg.probe('tiktok.mp4')['streams'][0]['width'])
    height = int(ffmpeg.probe('tiktok.mp4')['streams'][0]['height'])
    editStream = ffmpeg.input(random_video, stream_loop=-1)
    editStream = ffmpeg.filter(editStream, 'scale', width=str(width), height=-1)
    stream = ffmpeg.filter([targetStream, editStream], 'vstack', shortest='1')
    stream = ffmpeg.filter(stream, 'scale', width=str(width), height=str(height))
    stream = ffmpeg.filter(stream, 'setsar', 1)
    stream = ffmpeg.output(stream, targetStream.audio, 'output.mp4')
    ffmpeg.run(stream, cmd=['ffmpeg', '-vsync', '2'], overwrite_output=True, quiet=True)
    print("Finished stacking!")
    # compress video to 25 MB, Discord file size limit
    print("Compressing video...")
    compress_video('output.mp4', 'output-compressed.mp4', 25 * 1000)

# Function for handling the posting of the video
# See https://github.com/546200350/TikTokUploder
async def post(caption, filename):
    # Trim caption to fit TikTok character limit of 2200
    if (len(caption) > 2198 - len(target_user)):
        caption = caption[:2198 - len(target_user)]
    # Keep tags of initial video
    title = f"{caption[:caption.index('#')]}"
    tags = caption.split()
    tags = [tag[1:] for tag in tags if tag.startswith("#")]
    # Attempt to upload with sesison-id
    print(f"Trying to upload with session id: {session_id}")
    success = False
    try:
        uploadVideo(session_id, filename, title, tags, [target_user])
        success = True
    except KeyError: # session ID not valid (it has expired)
        traceback.print_exc()
        webhook = DiscordWebhook(url=webhook_url, content=f'<@{user_id}> Tried to upload, but session ID not valid! Need to update! ')
        webhook.execute()
    except: # server is busy
        traceback.print_exc()
        webhook = DiscordWebhook(url=webhook_url, content=f'<@{user_id}> Tried to upload, but server is busy.')
        webhook.execute()
    # send uploaded video in channel
    webhook = DiscordWebhook(url=webhook_url, content=f"@{target_user} {caption}")
    with open("output-compressed.mp4", "rb") as f:
        webhook.add_file(file=f.read(), filename='tiktok.mp4')
    webhook.execute()
    return success
    
# Function run every 20 minutes that checks if target user has uploaded new video
# See https://github.com/Russell-Newton/TikTokPy
async def run():
    now = datetime.datetime.now()
    print(f"{bcolors.OKBLUE}Checking for new videos... Time:{bcolors.ENDC} {now}")
    prevVideos = number
    async with AsyncTikTokAPI(emulate_mobile=True, navigation_retries=5, navigation_timeout=60000) as api:
        user = await api.user(target_user)
        if user is None:
            return
        numVideos = user.stats.video_count
        # Check if new video has been made
        if prevVideos < numVideos:
            videos = user.videos
            if videos is None:
                return
            # For all videos that have been missed, perform the remixing process
            for i in range(numVideos - prevVideos):
                video = await videos.fetch(numVideos - prevVideos - i - 1)
                print(f"{bcolors.HEADER}New video: {bcolors.ENDC}{video.desc[:20].strip()}... {bcolors.HEADER}Create Time: {bcolors.ENDC}{video.create_time}")
                # Skip slideshows, as the downloading breaks
                if video.image_post:
                    print(f"{bcolors.WARNING}New video is a slideshow, not creating another video!{bcolors.ENDC}")
                    # Update number of videos handled
                    dotenv.set_key(dotenv_file, "NUMBER", str(prevVideos + i + 1))
                    continue
                # Save video
                print(f"{bcolors.WARNING}Saving video...{bcolors.ENDC}")
                await save_video(f"https://www.tiktok.com/@{target_user}/video/{video.id}")
                print(f"{bcolors.OKGREEN}Successfully downloaded video!{bcolors.ENDC}")
                # Edit video
                print(f"{bcolors.WARNING}Editing video...{bcolors.ENDC}")
                edit_video()
                print(f"{bcolors.OKGREEN}Finished video!{bcolors.ENDC}")
                # Post video
                print(f"{bcolors.WARNING}Posting Video...{bcolors.ENDC}")
                success = await post(video.desc, "output.mp4")
                if success:
                    print(f"{bcolors.OKGREEN}Finished posting!{bcolors.ENDC}")
                else:
                    print(f"{bcolors.FAIL}Failed to post, manual upload is necessary{bcolors.ENDC}")
                print(f"{bcolors.WARNING}Cleaning up...{bcolors.ENDC}")
                # Clean up excess files that have been created
                os.remove("output.mp4")
                os.remove("tiktok.mp4")
                os.remove("output-compressed.mp4")
                for f in glob.glob("*.log"):
                    os.remove(f)
                for f in glob.glob("*.mbtree"):
                    os.remove(f)
                print(f"{bcolors.OKGREEN}Finished cleanup!{bcolors.ENDC}")
                # Update current number of files handled
                dotenv.set_key(dotenv_file, "NUMBER", str(prevVideos + i + 1))
        elif prevVideos > numVideos:
            # User has deleted some videos, so update count to match
            dotenv.set_key(dotenv_file, "NUMBER", str(numVideos))
            print(f"{bcolors.HEADER}No new video{bcolors.ENDC}")
        else:
            print(f"{bcolors.HEADER}No new video{bcolors.ENDC}")

# Discord Bot for allowing quick updating of TikTok session-ids
class MyBot(interactions.Client):
    @interactions.slash_command(
        name="update",
        description="Update TikTok Session ID",
        scopes=[guild_id],
        options=[
            interactions.SlashCommandOption(
                name="session_id",
                type=interactions.OptionType.STRING,
                description="TikTok Session ID",
                required=True
            )
        ]
    )
    async def update(self, ctx: interactions.SlashContext, session_id):
        dotenv.set_key(dotenv_file, "SESSION-ID", session_id)
        await ctx.send(f"Updated session_id to `{session_id}`")
        print(f"{bcolors.OKBLUE}Updated session_id to {bcolors.ENDC}{session_id}")
    @interactions.slash_command(
        name="current",
        description="Get Current TikTok Session ID",
        scopes=[guild_id]
    )
    async def current(self, ctx: interactions.SlashContext):
        session_id = os.environ['SESSION-ID']
        await ctx.send(f"Current session_id is : `{session_id}`")
        print(f"{bcolors.OKBLUE}Received request to print current session-id{bcolors.ENDC}")

# Start Discord bot
bot = MyBot(token=bot_token)

def run_bot():
    bot.start()

# Create a new thread for running the Discord bot while the main thread handles the listening for TikTok videos
t = threading.Thread(target=run_bot)
t.daemon = True
t.start()

# Use schedule package to time running of functions
# See https://github.com/dbader/schedule
def job():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())

def remind():
    webhook = DiscordWebhook(url=webhook_url, content=f"<@{user_id}> Reminder to update session ID soon! It's been one month!")
    webhook.execute()

schedule.every(20).minutes.do(job)
schedule.every(4).weeks.do(job)

job()
while True:
    schedule.run_pending()
    time.sleep(1)
    