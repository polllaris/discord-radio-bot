import json
import glob
import eyed3
import random
import asyncio
import discord
from io import BytesIO
from queue import Queue
from typing import Callable, List, Dict, Optional, Union, Tuple
from discord import FFmpegPCMAudio
from discord.ext import commands
from discord.errors import NotFound
from dataclasses import dataclass, field


class AlreadyVotedError(Exception):

	pass

class DefaultTokenError(Exception):

	pass

class NoTokenError(Exception):

	pass

class MissingTokenError(Exception):

	pass

class MissingSongDirectoryError(Exception):

	pass

class Embedded:

	def __init__(self,
		message:discord.Message,
		factory:Callable[[], Tuple[discord.Embed, Optional[discord.File]]]
	):

		self.message = message
		self.factory = factory

	async def delete(self) -> None:

		try:
			await self.message.delete()
		except NotFound:
			pass

	async def reembed(self) -> None:

		embed, file = self.factory()
		await self.message.edit(embed=embed, file=file)

class Embedder:

	def __init__(self, channels:List[discord.TextChannel], *factories):

		self.channels = channels
		self.factories = factories
		self.embedded:List[Embedded] = []

	async def cleanup(self) -> None:

		for embedded in self.embedded:
			await embedded.delete()

		self.embedded.clear()

	async def reembed(self) -> None:

		for embedded in self.embedded:
			await embedded.reembed()

	async def embed(self) -> None:

		"""
		Embeds an embed from all the factories
		and makes an Embedded object out of them
		adding to the embedded list.
		"""

		for factory in self.factories:
			for channel in self.channels:
				embed, file = factory()

				message = await channel.send(embed=embed, file=file)
				self.embedded.append(Embedded(message, factory))



@dataclass(eq=True, frozen=True)
class RadioSong:


	_artist:str
	_title:str
	_filepath:str
	_image_data:Optional[bytes] = None

	def __str__(self):

		return f"{self.artist} - {self.title}"


	@property
	def artist(self) -> str:

		if self._artist and self._title:
			artist = self._artist
		elif " - " in self.filename:
			artist = self.filename.split(" -", 1)[0]
		else:
			artist = "unknown"

		return artist

	@property
	def title(self) -> str:

		if self._title and self._artist:
			title = self._title
		elif " - " in self.filename:
			title = self.filename.split("- ", 1)[1].rsplit(".", 1)[0]
		else:
			title = "unknown"

		return title

	@property
	def filename(self):

		if "/" in self.filepath:
			filename = self.filepath.rsplit("/", 1)[1]
		elif "\\" in self.filepath:
			filename = self.filepath.rsplit("\\", 1)[1]
		else:
			filename = self.filepath

		return filename

	@property
	def filepath(self):

		return self._filepath

	@property
	def image_data(self):

		return self._image_data

	@staticmethod
	def from_file_mp3(filepath:str):

		tag = eyed3.load(filepath).tag

		try:
			image_data = tag.images[0].image_data
		except IndexError:
			image_data = None

		return RadioSong(tag.artist, tag.title, filepath, image_data)



def choose_random_songs(song_list:List[RadioSong], amount:Optional[int]=None) -> List[RadioSong]:

	new_song_list:List[RadioSong] = []

	while len(new_song_list) < (amount or len(song_list)):
		song = random.choice(song_list)
		if song in new_song_list: continue

		new_song_list.append(song)

	return new_song_list

class Broadcaster:

	voice_channel:discord.VoiceChannel
	voice_client:discord.VoiceClient = None
	audio_source:discord.FFmpegPCMAudio = None

	def __init__(self, voice_channel):

		self.voice_channel = voice_channel

	def is_connected(self):

		return self.voice_client and self.voice_client.is_connected()

	def is_paused(self):

		return self.voice_client and self.voice_client.is_paused()

	def is_playing(self):

		return self.voice_client and self.voice_client.is_playing()

	async def stop(self) -> None:

		self.voice_client.stop()

	async def init(self) -> None:

		self.voice_client = await self.voice_channel.connect()

	async def pause(self) -> None:

		self.voice_client.pause()

	async def play(self, song:RadioSong) -> None:

		source = FFmpegPCMAudio(song.filepath)
		self.voice_client.play(source)



class BroadcasterManager:
	broadcasters:List[Broadcaster]

	def __init__(self):

		self.broadcasters = []

	def add_broadcaster(self, broadcaster:Broadcaster) -> None:

		self.broadcasters.append(broadcaster)

	def is_playing(self):

		for broadcaster in self.broadcasters:
			if broadcaster.is_playing():
				return True


	async def stop(self) -> None:

		for broadcaster in self.broadcasters:
			if broadcaster.is_playing():
				await broadcaster.stop()

	async def play(self, song:RadioSong) -> None:

		for broadcaster in self.broadcasters:
			if not broadcaster.is_connected():
				await broadcaster.init()

			await broadcaster.play(song)

class RadioPlaylist:

	song_list:List[RadioSong]

	def __init__(self, song_list:List[RadioSong]):

		self.song_list = song_list

	def __len__(self):

		return len(self.song_list)

	@property
	def index(self):

		return self.song_list.index

	@property
	def __getitem__(self):

		return self.song_list.__getitem__

	def clear_song_list(self) -> None:

		self.song_list.clear()

	def shuffle_song_list(self) -> None:

		new_song_list:List[RadioSong] = []

		while len(new_song_list) < len(self.song_list):
			song = random.choice(self.song_list)
			if song in new_song_list: continue

			new_song_list.append(song)

		self.clear_song_list()
		self.song_list.extend(new_song_list)


	@staticmethod
	def from_directory(path:str):

		song_list = []

		for filepath in glob.glob(f"audio/*"):
			# radiobot only supports mp3 files at this time.
			if not filepath.endswith(".mp3"): continue

			song_list.append(RadioSong.from_file_mp3(filepath))

		return RadioPlaylist(song_list)


class RadioQueue:

	"""
	A class/object to manage the queueing of songs

	Multiple song selecting methods will have impact on instances
	of this class and make changes internally.

	Automatically shuffles the playlist when end is hit.
	"""


	def __init__(self, playlist:RadioPlaylist):

		self.playlist = playlist
		self.index = 0

	def shuffle(self):

		self.playlist.shuffle_song_list()

	def go_to_song(self, song:RadioSong) -> None:

		"""
		Shuffles the list and then switches the index
		to the one that song is at, effectively making
		the next song that one.
		"""

		self.index = self.playlist.index(song)

	def get_next_song(self) -> RadioSong:

		"""
		Returns the next song in the playlist
		after the index set in this queue.

		Sets index to 0 if next song index would
		be greater than the playlist length and shuffles the playlist
		"""

		if self.index < len(self.playlist):
			song = self.playlist[self.index]
			self.index += 1
		else:
			self.shuffle()
			song = self.playlist[0]
			self.index = 0

		return song


class RadioSongCandidate:

	song:RadioSong
	votes:int

	def __init__(self, song:RadioSong):

		self.song = song
		self.votes = 0

	def vote(self):

		self.votes += 1

class RadioSongVote:

	voters:List[discord.User]

	def __init__(self, playlist:RadioPlaylist, max:Optional[int]=5):

		self.candidates = []
		self.voters = []

		for song in choose_random_songs(playlist.song_list, max):

			candidate = RadioSongCandidate(song)
			self.candidates.append(candidate)

	def clear(self):

		self.candidates.clear()
		self.voters.clear()

	def vote(self, user:discord.User, index:int) -> None:

		if user in self.voters:
			raise AlreadyVotedError

		try:
			self.candidates[index - 1].vote()
		except IndexError:
			return

		self.voters.append(user)

	def winner(self):

		return max(self.candidates, key=lambda c: c.votes).song




@dataclass
class RadioConfig:

	discord_token:str
	song_directory:str
	# colors
	color_song_embed:int = 8675309
	color_vote_embed:int = 8675309

	# channels
	text_channels:List[int] = field(default_factory=list)
	voice_channels:List[int] = field(default_factory=list)
	# images
	image_default_cover:str = "https://i.ibb.co/YPktdZ2/cover-default.png"
	image_voting_thumbnail:str = "https://i.ibb.co/C9hCH2s/voting-default.jpg"
	# commands
	command_prefix:str = "!!"
	command_roles_skip:list = field(default_factory=list)
	# voting
	vote_after:int = 10
	vote_candidates:int = 5

	@staticmethod
	def from_file_json(filepath):

		with open(filepath, "r") as f:
			settings = json.load(f)

		if "discord_token" in settings:
			token = settings["discord_token"]
		else:
			raise MissingTokenError

		if token == "token-here":
			raise DefaultTokenError
		elif token == "":
			raise NoTokenError

		if "song_directory" not in settings:
			raise MissingSongDirectoryError


		return RadioConfig(**settings)
class Radio:

	client:commands.Bot
	playlist:RadioPlaylist
	queue:RadioQueue
	broadcaster_manager:BroadcasterManager

	current_song:Optional[RadioSong] = None
	current_vote:Optional[RadioSongVote] = None

	song_embedder:Optional[Embedder] = None
	vote_embedder:Optional[Embedder] = None

	flag_skip_song:bool = False
	flag_song_skipped:bool = False

	def __init__(self, client:commands.Bot, config:RadioConfig):

		self.client = client
		self.config = config
		self.playlist = RadioPlaylist.from_directory(config.song_directory)
		self.playlist.shuffle_song_list()
		self.queue = RadioQueue(self.playlist)
		self.broadcaster_manager = BroadcasterManager()

	def add_voice_channel(self, channel:discord.VoiceChannel) -> None:

		broadcaster = Broadcaster(channel)
		self.broadcaster_manager.add_broadcaster(broadcaster)

	async def skip(self) -> None:

		"""
		Skips the current playing song.

		Triggers the started radio loop
		to tell the broadcaster to stop the song.
		"""

		self.flag_skip_song = True

		skip_song = self.current_song
		while self.current_song == skip_song:
			await asyncio.sleep(0.8)

		if self.flag_song_skipped:
			self.flag_song_skipped = False

	async def play(self, song:RadioSong) -> None:

		"""
		Tells the broadcast manager to play the song
		to all voice channels.
		"""

		await self.broadcaster_manager.play(song)

	async def start(self):


		text_channels = [self.client.get_channel(c) for c in self.config.text_channels]
		voice_channels = [self.client.get_channel(c) for c in self.config.voice_channels]

		for voice_channel in voice_channels:
			self.add_voice_channel(voice_channel)

		for text_channel in text_channels:
			await text_channel.purge(check=lambda m: m.author == self.client.user)

		def song_embed_factory() -> Tuple[discord.Embed, Optional[discord.File]]:

			embed = discord.Embed(title=self.current_song.title, color=self.config.color_song_embed)
			embed.set_author(name=self.current_song.artist)

			if self.current_song.image_data is None:
				file = None
				thumbnail_url = self.config.image_default_cover
			else:
				file = discord.File(BytesIO(self.current_song.image_data), filename="cover.jpg")
				thumbnail_url = "attachment://cover.jpg"

			embed.set_thumbnail(url=thumbnail_url)

			return (embed, file)

		def vote_embed_factory() -> Tuple[discord.Embed, None]:

			embed = discord.Embed(title="Next Song Vote", color=self.config.color_vote_embed)

			for index, candidate in enumerate(self.current_vote.candidates):
				song = candidate.song

				embed.add_field(
					name=f"{index + 1}) | votes: {candidate.votes}",
					value=f"{song.artist} - {song.title}",
					inline=False,
				)

			embed.set_thumbnail(url=self.config.image_voting_thumbnail)

			return (embed, None)

		while True:

			self.current_song = self.queue.get_next_song()
			self.song_embedder = Embedder(text_channels, song_embed_factory)

			# play the song and set the discord status
			await self.play(self.current_song)
			await self.client.change_presence(activity=discord.Game(name=self.current_song))

			if self.queue.index % self.config.vote_after == 0:
				self.current_vote = RadioSongVote(self.playlist, self.config.vote_candidates)
				self.vote_embedder = Embedder(text_channels, vote_embed_factory)
			else:
				self.current_vote = None
				self.vote_embedder = None


			if self.song_embedder is not None:
				await self.song_embedder.embed()

			if self.vote_embedder is not None:
				await self.vote_embedder.embed()

			while self.broadcaster_manager.is_playing():
				if self.flag_skip_song:
					self.flag_skip_song = False
					self.flag_song_skipped = True

					await self.broadcaster_manager.stop(); break

				await asyncio.sleep(0.5)

			if self.song_embedder is not None:
				await self.song_embedder.cleanup()

			if self.vote_embedder is not None:
				await self.vote_embedder.cleanup()

			if self.current_vote is not None:
				winning_song = self.current_vote.winner()
				self.queue.shuffle()
				self.queue.go_to_song(winning_song)
				self.current_vote = None

class RadioCog(commands.Cog):

	client:commands.Bot
	radio:Radio

	# commands.Cog
	qualified_name = "Radio"

	def __init__(self, client:commands.Bot, config:RadioConfig):

		self.client = client
		self.radio = Radio(client, config)
		self.config = config

	@commands.Cog.listener()
	async def on_ready(self) -> None:

		await self.radio.start()

	@commands.command(name="vote")
	async def on_command_vote(self, ctx, index:int) -> None:

		try:
			await ctx.message.delete()
		except NotFoundError:
			pass

		try:
			self.radio.current_vote.vote(ctx.author, index if index > 0 else index - 1)
			await self.radio.vote_embedder.reembed()
		except (IndexError, AlreadyVotedError):
			return


def main():

	import argparse

	parser = argparse.ArgumentParser()
	parser.add_argument("-f", "--config-file", help="path to json config file")

	arguments = parser.parse_args()

	if not arguments.config_file:
		exit("please provide a path to a json config with argument -f /path/file.json")

	try:
		config = RadioConfig.from_file_json(arguments.config_file)
	except MissingTokenError:
		exit("discord_token is missing in your config! please add it.")
	except DefaultTokenError:
		exit("discord_token in your config is the placeholder! please change it to your bot token.")
	except NoTokenError:
		exit("discord_token is empty in your config! please change it to your bot token.")
	except MissingSongDirectoryError:
		exit("song_directory is missing from your config ! please add it.")

	# taking care of verbosity for about everything the user could possibly have messed up in the config.
	if not len(glob.glob(f"{config.song_directory}/*.mp3")) > 0:
		exit("song directory empty! please add mp3's to it.")

	if not config.voice_channels:
		exit("voice_channels list empty! please add the ids of voice channels to stream to.")

	# check if all of the voice channel ids were added as integers
	for channel_id in config.voice_channels:
		if type(channel_id) == int: continue

		exit("voice channel ids need to be integers not strings! please remove the quotes.")

	if not config.text_channels:
		exit("text_channels list empty! please add the ids of the text channels for embeds")

	# check if all of the text channel ids were added as integers
	for channel_id in config.text_channels:
		if type(channel_id) == int: continue

		exit("text channel ids need to be integers not strings! please remove the quotes.")

	# start the discord bot/client.
	client = commands.Bot(command_prefix=config.command_prefix)
	client.add_cog(RadioCog(client, config))
	client.run(config.discord_token)

if __name__ == "__main__":

	main()
