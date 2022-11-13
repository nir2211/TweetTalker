import os
import re
from os.path import join, dirname
import tweepy
from dotenv import load_dotenv
from gtts import gTTS
from pydub import AudioSegment
import urllib.request
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
import textwrap
from moviepy.editor import ImageClip, concatenate_videoclips, VideoFileClip, AudioFileClip

TEXT_WIDTH = 60


# Refer this page for twitter app account: https://developer.twitter.com/en/portal/products/elevated
# Other References:
# https://py-googletrans.readthedocs.io/en/latest/
# https://towardsdatascience.com/how-to-extract-data-from-the-twitter-api-using-python-b6fbd7129a33
# https://superuser.com/questions/490922/merging-two-fonts
def read_timeline():
    dotenv_path = join(dirname(__file__), '.env')
    load_dotenv(dotenv_path)

    consumer_key = os.environ["API_KEY"]
    consumer_secret = os.environ["API_KEY_SECRET"]
    access_token = os.environ["ACCESS_TOKEN"]
    access_token_secret = os.environ["ACCESS_TOKEN_SECRET"]

    auth = tweepy.OAuth1UserHandler(
      consumer_key,
      consumer_secret,
      access_token,
      access_token_secret
    )

    api = tweepy.API(auth)
    tweets = [row for row in api.home_timeline(tweet_mode='extended')][::-1]
    clear_tmp()
    clear_videos()
    try:
        os.remove('tweet_video.mp4')
    except OSError as e:
        pass
    for i, tweet in enumerate(tweets):
        images, clips = download_media(tweet)
        text = tweet.full_text
        load_tweet_image(tweet.author.screen_name, text)
        text = re.sub(r'http\S+', '', text).replace('#', '')
        # duration = tweet_talk(tweet.author.screen_name, text, tweet.lang, i)
        duration = tweet_talk(tweet.author.screen_name, text, tweet.lang, 0)
        if duration > 0:
            create_clip(i, images if images else ['tmp/board.jpeg'], clips, duration)
        print(tweet.author.screen_name, tweet.full_text)
        clear_tmp()
    concat_clips()
    clear_videos()


def clear_tmp():
    for filename in os.listdir('tmp'):
        file_path = os.path.join('tmp', filename)
        try:
            if not os.path.isdir(file_path):
                os.remove(file_path)
        except OSError as e:
            pass


def clear_videos():
    for filename in os.listdir('tmp/videos'):
        file_path = os.path.join('tmp/videos', filename)
        try:
            if not os.path.isdir(file_path):
                os.remove(file_path)
        except OSError as e:
            pass


def create_clip(index, images, clips, duration):
    videos = [VideoFileClip(clip).resize((1280, 720)) for clip in clips]
    # creating slide for each image
    slides = [ImageClip(image, duration=duration/len(images)) for image in images]
    # concatenating slides
    slide_clips = concatenate_videoclips(slides, method='compose') \
        if len(images) > 1 else slides[0]
    try:
        audio_background = AudioFileClip('tmp/res.mp3')
    except IOError as e:
        print('IO Error {}'.format(str(e)))
        return
    # final_audio = CompositeAudioClip([my_clip.audio, audio_background])
    final_clip = slide_clips.set_audio(audio_background)
    # final_clip.write_videofile('tmp/cur_video.mp4', fps=24)
    # final_clip = VideoFileClip('tmp/cur_video.mp4')
    all_clips = [final_clip]
    if videos:
        all_clips = [final_clip] + videos
    if len(all_clips) > 1:
        final_clip = concatenate_videoclips(all_clips)
    # exporting final video
    final_clip.write_videofile('tmp/videos/%s.mp4' % str(index), fps=24)


def concat_clips():
    paths = [os.path.join('tmp/videos', filename) for filename in os.listdir('tmp/videos')]
    paths.sort(key=lambda x: int(x.rsplit('/')[-1].split('.')[0]))

    videos = [VideoFileClip(path) for path in paths]
    final_video = concatenate_videoclips(videos)
    # exporting final video
    final_video.write_videofile('tweet_video.mp4', fps=24)


def load_tweet_image(author, tweet):
    # Importing the PIL library

    # Open an Image
    img = Image.open('board.jpeg').resize((1280, 720))

    # Call draw Method to add 2D graphics in an image
    I1 = ImageDraw.Draw(img)

    # Custom font style and font size
    font = ImageFont.truetype('fonts/noto-sans/NotoSansMergedAll.ttf', 30)

    lines = textwrap.wrap(author + ': ' + tweet, TEXT_WIDTH, break_long_words=False)
    line_spacing = 55
    y = 200
    for line in lines:
        # Add Text to an image
        I1.text((75, y), line, font=font, fill=(0, 0, 0))
        y += line_spacing

    # # Display edited image
    # img.show()

    # Save the edited image
    img.save("tmp/board.jpeg")


def tweet_talk(author, tweet, lang, index):
    if not tweet:
        print('Tweet is empty.')
        return 0
    chunk1 = gTTS(text=author + ' says..', lang='en', slow=False)
    chunk1.save("tmp/author.mp3")
    try:
        chunk1 = gTTS(text=tweet, lang=lang, slow=False)
    except ValueError as e:
        print('Lang {} not recognized. Falling back to Tamil.'.format(lang))
        chunk1 = gTTS(text=tweet, lang='ta', slow=False)
    # Saving the converted audio in a mp3
    try:
        chunk1.save("tmp/tweet.mp3")
    except AssertionError as e:
        print("Assertion error skipping tweet.")
        return 0

    part1 = AudioSegment.from_mp3("tmp/author.mp3")
    one_sec_silence = AudioSegment.silent(duration=1000)
    part2 = AudioSegment.from_mp3("tmp/tweet.mp3")
    whole = part1 + one_sec_silence + part2 + one_sec_silence
    if index:
        try:
            whole = AudioSegment.from_mp3("tmp/res.mp3") + one_sec_silence + whole
        except Exception as e:
            pass
    whole.export("tmp/res.mp3", format="mp3")
    return whole.duration_seconds


def download_media(tweet):
    if not hasattr(tweet, 'extended_entities') or 'media' not in tweet.extended_entities:
        return list(), list()
    images, clips = list(), list()
    for i, media in enumerate(tweet.extended_entities['media']):
        if 'video_info' in media:
            bit_rate, video_url = 0, None
            for j, variant in enumerate(media['video_info']['variants']):
                br = variant['bitrate'] if 'bitrate' in variant else 0
                if br > bit_rate:
                    bit_rate = br
                    video_url = variant['url']
            if video_url:
                suffix = video_url.rsplit('.', 1)[-1]
                suffix = suffix.split('?')[0]
                path = 'tmp/' + str(i) + '.' + suffix
                urllib.request.urlretrieve(video_url, path)
                clips.append(path)
        else:
            img_path = 'tmp/' + str(i) + '.' + media['media_url'].rsplit('.', 1)[-1]
            urllib.request.urlretrieve(media['media_url'],
                                       img_path)
            Image.open(img_path).resize((1280, 720)).save(img_path)
            images.append(img_path)
    return images, clips


if __name__ == '__main__':
    read_timeline()
