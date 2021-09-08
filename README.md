# A semi customizable music streaming bot


Start a radio in your discord servers, stream mp3s to multiple servers 24/7 \
customize embed colors, voting thumbnail and more!

<b>THIS SCRIPT REQUIRES THE FOLLOWING MODULES:</b>

<ul>
	<li>discord</li>
	<li>eyed3</li>
	<li>PyNaCl</li>
</ul>

<b>NOTE:</b> \
[You will need to have ffmpeg installed and in your environment path
in order for the discord module to be able to stream audio.](https://www.thewindowsclub.com/how-to-install-ffmpeg-on-windows-10)


## CONFIGURATION

You can configure this bot to your liking by editing
the "fillme.json" in the config directory.

Configuration Options Include:
<pre>
discord_token:	
	the authenticaten token for the discord bot account.
song_directory:
	a path to a directory to load music from.
color_song_embed:
	a decimal color value for the embed of songs.
color_song_vote:
	a decimal color value for the embed of votes.
image_default_cover: 
	a link to an image for cover art to use
	as the thumbnail on the song embed when 
	there isn't one in the music file.
image_voting_thumbnail:
	a link to an image to use for the thumbnail
vote_after:
	how many songs before starting a vote for next song.
text_channels:
	a list of ids of text channels to place embeds in.
voice_channels:
	a list of ids of voice channels to stream music to.
command_prefix:
	the prefix to use for bot commands i.e. !! vote
</pre>



### BEHAVIOR

The bot will start, it will load music into a playlist from the \
song_directory, it will then shuffle the playlist and wrap it in a queue.

The next song will be gotten from the queue and played to the voice_channels, \
an embed will be posted with the song artist, title and cover art in the text_channels.


Every vote_after songs a vote will be had with up to five songs from the playlist to pick \
from, the one with the highest vote will be played next and the queue/playlist will be shuffled.

If/when last song in the playlist/queue is reached, the playlist is reshuffled and starten over.

#### RUNNING



<pre>
python discord-radio-bot.py -f config/fillme.json
</pre>



##### WHERE TO GET FREE MUSIC

You can obtain music to stream for free from from NoCopyrightSounds \
https://www.youtube.com/c/NoCopyrightSounds/videos

###### DISCLAIMER
<pre>
This bot is intended for use with music that is in the public domain,
creative commons/attribute required OR that you have the licensing to stream!
</pre>
