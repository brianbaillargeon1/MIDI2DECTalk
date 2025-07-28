#!/usr/bin/env python

"""
Main program; for details, see README.md
"""

# ==== DEPENDENCIES ====

# https://pypi.org/project/MIDIFile/
# Can be obtained via `pip3 install MIDIFile`

# lexconvert.py and eSpeak, see README.md

import math
import MIDI # type: ignore
import os
import sys
import time
from subprocess import Popen, PIPE
from typing import NamedTuple
from typing import NewType
from typing import Optional
from types import SimpleNamespace


# ==== CONFIGURATION ====

# Set to True to print debug information to STDOUT
DEBUG = True

# Pauses the program for this many seconds if there's an error
PAUSE_ON_ERROR_DURATION = 0

# Location of input files
INPUT_DIRECTORY = "input"

# Name of the file containing lyrics to be converted to phonemes
LYRICS_INPUT_FILENAME = "Lyrics.txt"

# Name of the MIDI file that the phonemes will sync to
MIDI_INPUT_FILE = "Melody.mid"

# Location of the output file
OUTPUT_DIRECTORY = "output"
OUTPUT_FILENAME = "Output.spk"

# Default duration of consonant phonemes in milliseconds
DEFAULT_CONSONANT_DURATION = 90

# Set this for consonant phonemes that sound better with a duration other than the default
CONSONANT_DURATIONS: dict[str, int] = {}
# Example: CONSONANT_DURATIONS = {'g':85, 'wr':95}

# Translates phonemes produced by lexconvert.py into phonemes supported by the targeted DECTalk capable technology.
# Default: target the phonetic symbols list on page 44 of the dectalk-guide.
# I.e. lexconvert.py produces 'l', but the dectalk-guide includes only 'll':
# https://www.digikey.com/htmldatasheets/production/1122220/0/0/1/dectalk-guide.html
PHONEME_CONVERSION = {'l':'ll'}

# Determines whether to write "[:phoneme on]" at the start of the output file.
# This may be needed depending on the target technology.
WRITE_PHONEME_ON = False

# Track number in the MIDI file to use
TRACK_NUMBER = 0

# Whether to treat NOTE_ON with velocity 0 as NOTE_OFF
VEL_ZERO_IS_NOTE_OFF = False

# Whether NOTE_OFF events should be handled regardless of whether their pitch corresponds to a sustained NOTE_ON event
IGNORE_NOTE_OFF_PITCH = True

# ==== CONSTANTS ====

# Categorization of "dectalk" dictionary in lexconvert.py into vowels and consonants.
# The order is important to prevent ambiguity. I.e. 'lx' comes before 'l', 'rx' comes before 'r', etc.
# lexconvert.py includes 'ihr', but explains that it parses to 'ih', and 'r'; I have omitted it.
VOWELS = ['aa', 'ae', 'ah', 'ao', 'aw', 'ax', 'ay', 'eh', 'el', 'ey', 'ih', 'ix', 'iy', 'ow', 'oy', 'rr', 'uh', 'uw', 'yx', 'yu']

CONSONANTS = ['b', 'ch', 'dx', 'dh', 'd', 'f', 'g', 'hx', 'q', 'jh', 'k', 'lx', 'l', 'm', 'nx', 'n', 'p', 'rx', 'r', 'sh', 's', 'tx', 'th', 't', 'v', 'w', 'zh', 'z']

# Phoneme representing silence
REST = '_'

# A440 in MIDI: 69, A440 in DECTalk: 34. Their difference: 35
MIDI_DECTALK_PITCH_DELTA = 35

# For identifying the MIDI event types.
UNUSED = -1
NOTE_ON = 144
NOTE_OFF = 80


# ==== TYPES ====

Category = SimpleNamespace()
Category.vowel = 'V'
Category.consonant = 'C'
Category.comma = ','


class Phoneme(NamedTuple):
	"""
	Represents a phoneme, and its category. E.g. Phoneme('hx', 'C') is the 'hx' phoneme, categorized as a consonant
	"""
	phoneme: str
	category: str

class CategoryMatch(NamedTuple):
	"""
	A type used for parsing and categorizing phonemes
	"""
	phoneme: Phoneme
	remainder: str

# Represents a list a Phonemes containing exactly one vowel
Syllable = NewType('Syllable', list[Phoneme])

# ==== FUNCTIONS ====

def debug(message: str):
	""" Prints a message if DEBUG is enabled """
	if DEBUG:
		print(message)

def info(message: str):
	""" Prints a message """
	print(message)

def error(message: str):
	""" Prints a message to stderr """
	print(message, file=sys.stderr)
	if PAUSE_ON_ERROR_DURATION:
		time.sleep(PAUSE_ON_ERROR_DURATION)

def split_on_category_match(phonemes: str, category: str, category_tokens: list[str], match_apostrophe: bool) -> Optional[CategoryMatch]:
	"""
	Checks if phonemes starts with a token in the category list
	Params:
	phonemes: an str like 'hxehl'ow, w'rrld'.
	category: represents the category we're attempting to split on, E.g. Category.vowels, Category.consonants.
	category_tokens: the list of possible tokens in the category, E.g. one of the constant lists VOWELS or CONSONANTS.
	match_apostrophe: whether or not matching tokens might be prefixed with an apostrophe.

	Returns:
	A tuple: (matching phoneme, phoneme list with the match removed)
	E.g. ("hx", "ehl'ow, w'rrld")
	If no category match, returns None
	"""

	remainder = phonemes
	match = ''

	if match_apostrophe and phonemes[0] == '\'':
		match = '\''
		remainder = phonemes[1:]

	for token in category_tokens:
		if remainder.startswith(token):
			match = match + token
			remainder = remainder[len(token):]
			phoneme = Phoneme(match, category)
			return CategoryMatch(phoneme, remainder)
	return None

def categorize_phonemes(phonemes: str) -> list[Phoneme]:
	"""
	Parses phonemes, and categorizes them into vowels, constants, and commas
	(commas represent word endings).
	Params:
	phonemes: an str like 'hxehl'ow, w'rrld'.

	Returns
	a list of Phonemes whose category is one of the constants: Category.vowel, Category.consonant, or Category.comma.
	"""

	unparsed = phonemes
	categorized_phonemes = []
	category_match = None

	while unparsed:
		category_match = split_on_category_match(unparsed, Category.vowel, VOWELS, True)
		if not category_match:
			category_match = split_on_category_match(unparsed, Category.consonant, CONSONANTS, False)
		if not category_match:
			category_match = split_on_category_match(unparsed, Category.comma, [", "], False)

		if category_match:
			categorized_phonemes.append(category_match.phoneme)
			unparsed = category_match.remainder
		else:
			error("Error parsing phonemes; could not find a match at the start of: " + unparsed)
			break

	return categorized_phonemes

def parse_phonemes(phonemes: str) -> list[Syllable]:
	"""
	Parses the param 'phonemes', an str like 'hxehl'ow, w'rrld',
	and returns a list of Syllables.
	We define a syllable as a group of phonemes containing exactly one vowel.
	For example, with input hxehl'ow, w'rrld, we would return:
	[['hx', 'eh'], ['l', '\'ow'], ['w', '\'rr', 'l', 'd']]
	"""

	# Return value
	parsed: list[Syllable] = []
	# Buffer for a syllable as it's being parsed in the loop below
	syllable_phonemes: list[Phoneme] = []

	categorized_phonemes = categorize_phonemes(phonemes)
	debug("Categorized Phonemes:\n" + str(categorized_phonemes))

	# Iterate over the categorized_phonemes and buffer them into syllable_phonemes.
	# We've completed a syllable when we've reached one of the following conditions:
	# 1) we've hit a comma (I.e. the end of a word)
	# 2) syllable_phonemes contains a vowel, and we're about to read a second vowel
	# 3) the end of categorized_phonemes has been reached

	consonants_between_vowels = 0
	vowel_present = False
	for phoneme in categorized_phonemes:
		match phoneme.category:
			case Category.comma:
				# Word endings are syllable endings
				if syllable_phonemes:
					parsed.append(Syllable(syllable_phonemes))
				consonants_between_vowels = 0
				vowel_present = False
				syllable_phonemes = []

			case Category.consonant:
				syllable_phonemes.append(phoneme)
				consonants_between_vowels+=1

			case Category.vowel:
				if vowel_present:
					# We have encountered a second vowel; start a new syllable

					# Obervations about when phonemes sound when singing:
					# If there's a single consonant between vowels, the consonant tends to start the second syllable.
					# E.g. [hx, eh, l, 'ow] -> [hx, eh] [l, 'ow]

					# However, if there's an odd number of consonants between vowels,
					# they tend to cluster at the end of the first syllable.
					# "firstly", -> [f, rr]  *[s, t, l]* [ih, ...]    -> [f, 'rr, s, t], [l, ih]
					# "helpful"  -> [hx, eh] *[l, p, f]* [uh, l, ...] -> [hx, 'eh, l, p], [f, uh, l]
					# But there are counterexamples
					# E.g. "Fulcrum" should ideally become: [f, ah, l] [k, r, ax, m]

					# Note: lexconvert has some syllable separating capabilities, E.g. this exists:
					# python3 lexconvert.py --syllables "Fulcrum"
					# But the output is "fulc rum".
					# I considered using a dictionary file containing words with delimiters between syllables,
					# but splitting words into syllables before calling lexconvert would ruin pronunciations.
					# Calling lexconvert, then attempting to map english syllables to the converted phonemes is imperfect as well.

					if consonants_between_vowels == 0:
						# Two consecutive vowels, start a new syllable
						parsed.append(Syllable(syllable_phonemes))
						syllable_phonemes = []
					elif consonants_between_vowels == 1:
						# A single consonant between vowels: [hx, eh] *l* [ow, ...]"
						# Individual consonants tend to start syllables: [hx, eh], [l, oh, ...]
						parsed.append(Syllable(syllable_phonemes[:-1]))
						syllable_phonemes = [syllable_phonemes[-1]]
					else:
						# Suitable for the majority of words (cases like "firstly", "helpful"):
						# Put ceil(consonants/2) on the first syllable, and floor(consonants/2) on the second syllable
						num_second_word_consonants = math.floor(consonants_between_vowels/2)
						second_word_consonants = syllable_phonemes[-num_second_word_consonants:]
						parsed.append(Syllable(syllable_phonemes[:-num_second_word_consonants]))
						syllable_phonemes = second_word_consonants

				syllable_phonemes.append(phoneme)
				vowel_present = True
				consonants_between_vowels = 0

	if syllable_phonemes:
		parsed.append(Syllable(syllable_phonemes))

	debug("Parsed:\n" + str(parsed))

	return parsed

def get_event_type(event) -> int:
	"""
	Gets a MIDI event's effective event type.
	NOTE_ON with velocity 0 returns NOTE_OFF.
	Returns NOTE_ON, NOTE_OFF, or UNUSED
	"""
	if VEL_ZERO_IS_NOTE_OFF and event.header == NOTE_ON and event.message.velocity == 0:
		return NOTE_OFF

	if event.header in (NOTE_OFF, NOTE_ON):
		return event.header

	return UNUSED

def calculate_midi_pitch(note: MIDI.Events.messages.notes.Note) -> int:
	""" Takes a Note instance and gets its MIDI pitch number (E.g. A440 returns 69) """
	# Consider A440:
	# It is represented as 'a5'; its MIDI pitch is #69
	# 5 octaves * 12 pitches / octave + 9 pitches = 69 pitches
	notes = MIDI.Events.messages.notes.Note.notes
	return note.octave*12 + notes.index(note.note)

def calculate_dectalk_pitch(note: MIDI.Events.messages.notes.Note) -> int:
	""" Takes a Note instance and gets its DECTalk pitch number (E.g. A440 returns 34) """
	return calculate_midi_pitch(note) - MIDI_DECTALK_PITCH_DELTA

def get_event_time_millis(event: MIDI.Events.event.Event, tempo, ticks_per_beat, first_note_ticks) -> float:
	"""
	Takes a MIDI event and returns its time in milliseconds
	event: MIDI Event
	tempo: beats per minute
	ticks_per_beat: how many MIDI ticks per beat
	first_note_ticks: how many MIDI ticks elapsed before the first note
	"""
	time_in_ticks = event.time
	if first_note_ticks:
		time_in_ticks -= first_note_ticks
	# beats = ticks / (ticks / beats)
	beats_elapsed = time_in_ticks / ticks_per_beat
	# milliseconds = beats / (beats / minute) * (60 seconds / minute) * (1000 ms / second)
	return 60000 * beats_elapsed / tempo

def get_converted_phoneme(phoneme: str) -> str:
	""" Translates phonemes produced by lexconvert.py to phonemes supported by the targeted technology """
	if phoneme in PHONEME_CONVERSION:
		return PHONEME_CONVERSION[phoneme]
	return phoneme

def get_consonant_duration(consonant: str) -> int:
	"""
	Checks for a mapping for this consonant in CONSONANT_DURATIONS.
	Returns the default consonant duration if no mapping is specified.
	"""
	key = consonant
	if key in CONSONANT_DURATIONS:
		return CONSONANT_DURATIONS[key]
	return DEFAULT_CONSONANT_DURATION

def translate_syllable_to_dectalk(syllable: Syllable, note: MIDI.Events.messages.notes.Note, duration: int) -> str:
	"""
	Translates a syllable into the output format.
	Example syllable: [('w', 'c'), ('\'rr', 'v'), ('l', 'c'), ('d', 'c')]
	If the note is A440, and the duration is 500ms; this would be returned as:
	w<90>'rr<230,34>ll<90>d<90>
	"""

	output_text = ""

	total_consonant_duration = 0
	for phoneme in syllable:
		if phoneme.category == Category.consonant:
			converted_phoneme = get_converted_phoneme(phoneme.phoneme)
			total_consonant_duration += get_consonant_duration(converted_phoneme)

	vowel_duration = duration - total_consonant_duration
	if vowel_duration < 0:
		error("Could not fit all the phonemes within " + str(duration) + " milliseconds.")
		error("Consider reducing DEFAULT_CONSONANT_DURATION, or ensure your MIDI notes are sufficiently long.")
		#TODO: Call a cleanup method to close all the files
		sys.exit()

	for phoneme in syllable:
		converted_phoneme = get_converted_phoneme(phoneme.phoneme)
		if phoneme.category == Category.consonant:
			consonant_duration = int(get_consonant_duration(converted_phoneme))
			output_text += f"{converted_phoneme}<{consonant_duration}>"
		elif phoneme.category == Category.vowel:
			duration = int(vowel_duration)
			dectalk_pitch = calculate_dectalk_pitch(note)
			output_text += f"{converted_phoneme}<{duration},{dectalk_pitch}>"

	return output_text

def get_dectalk_rest(duration: int) -> str:
	""" Gets a rest for the specified duration in the output format """
	return REST + '<' + str(int(duration)) + '>'


# pylint: disable=R0912,R0914,R0915
def main():
	"""
	Main Program
	"""

	# Get the BPM
	tempo = float(input("What's the BPM? "))
	# Precise sync'ing may be needed. Support decimals - use float.
	# TODO: add support to read tempo meta messages.


	# Convert lyrics into DECTalk phonemes:
	# TODO: Exception handling
	lyrics = ""
	lyrics_file_path = os.path.join(INPUT_DIRECTORY, LYRICS_INPUT_FILENAME)
	with open(lyrics_file_path, 'r', encoding='utf-8') as lyrics_file:
		lyrics = lyrics_file.read()

	# TODO: Exception handling
	lex_convert_output = None
	with Popen(["lexconvert", "--phones", "dectalk", lyrics], stdout=PIPE) as process:
		(lex_convert_output, err) = process.communicate()
		if err:
			error(f"lexconvert error: {err}")

		exit_code = process.wait()
		if exit_code != 0:
			error(f"lexconvert exit code: {exit_code}")

	# Clean up output, and unify the delimiters between words as commas
	lex_convert_phonemes = lex_convert_output.decode('UTF-8')
	lex_convert_phonemes = lex_convert_phonemes.replace("[:phoneme on]\n[", "", 1)
	lex_convert_phonemes = lex_convert_phonemes.replace("] [", ", ")
	lex_convert_phonemes = lex_convert_phonemes.replace("]\n[", ", ")
	lex_convert_phonemes = lex_convert_phonemes.replace("]", "")
	lex_convert_phonemes = lex_convert_phonemes.replace("\n", "")
	debug("Phonemes:\n" + str(lex_convert_phonemes))


	# Convert the phonemes into a list of syllables
	parsed_syllables = parse_phonemes(lex_convert_phonemes)


	# Read the MIDI file, and parse the MIDI track whose events will be iterated
	# TODO: Exception handling
	midi_file_path = os.path.join(INPUT_DIRECTORY, MIDI_INPUT_FILE)
	midi_in = MIDI.MIDIFile(midi_file_path)
	midi_in.parse()

	# Ticks per beat of the BPM
	ticks_per_beat = float(midi_in.division.ticksPerCrotchet)
	debug("Ticks per beat: " + str(ticks_per_beat))

	if TRACK_NUMBER == 0 and len(midi_in) > 1:
		info("Multiple tracks detected; only the first track will be used")
	elif TRACK_NUMBER >= len(midi_in):
		error("The configured TRACK_NUMBER exceeds the highest track number in the MIDI file")
		# TODO: cleanup
		sys.exit()

	track = midi_in[TRACK_NUMBER]
	track.parse()


	# The output file's contents
	output = ""
	if WRITE_PHONEME_ON:
		output += "[:phoneme on]\n"
	output += "["


	# High level idea:
	# Iterate over the MIDI Events.
	# Every NOTE_ON starts a new syllable,
	# and it sustains until the next NOTE_ON or its corresponding NOTE_OFF.

	# To iterate through the syllables; increments each time we output a note.
	next_syllable_index = 0

	# It's common for the first note in a MIDI file to be delayed by a number of ticks.
	# We'd rather not start the output file with a leading rest.
	# Once the first note's time is detected, all timing will be shifted earlier this many ticks.
	# This way, the output begins immediately.
	first_note_ticks = None

	# As we iterate through MIDI events, this is the entity that has last started sustaining.
	# Its value can be REST, or a MIDI.Events.messages.notes.Note
	sustained_entity = None
	# The time in milliseconds that sustained_entity begins sustaining in the output file.
	# This is the sum of the durations that have been output so far.
	start_of_sustain = 0

	for event in track:
		event_type = get_event_type(event)

		# TODO: handle if event type is either NOTE_ON or NOTE_OFF, but there are no more syllables (I.e. add some 'ooh yeahs')

		if event_type == NOTE_ON:
			if not first_note_ticks:
				first_note_ticks = event.time

			if next_syllable_index >= len(parsed_syllables):
				error("There are more MIDI notes than syllables; output might be truncated")
				break

			event_time_millis = get_event_time_millis(event, tempo, ticks_per_beat, first_note_ticks)

			if sustained_entity:
				# Output the sustained entity, then start sustaining the new one
				duration = round(event_time_millis - start_of_sustain, 0)
				if sustained_entity == REST:
					syllable = get_dectalk_rest(duration)
					output += syllable
					debug(f"Syllable {syllable}")
				else:
					syllable = translate_syllable_to_dectalk(parsed_syllables[next_syllable_index], sustained_entity, duration)
					output += syllable
					debug(f"Syllable {syllable}")
					next_syllable_index += 1
				start_of_sustain += duration

			sustained_entity = event.message.note
		elif event_type == NOTE_OFF and sustained_entity:
			if IGNORE_NOTE_OFF_PITCH or (sustained_entity.note == event.message.note.note and sustained_entity.octave == event.message.note.octave):
				# This NOTE_OFF event ends sustained_entity. Write the entity, then begin a rest.
				event_time_millis = get_event_time_millis(event, tempo, ticks_per_beat, first_note_ticks)
				duration = int(round(event_time_millis - start_of_sustain, 0))
				syllable = translate_syllable_to_dectalk(parsed_syllables[next_syllable_index], sustained_entity, duration)
				debug(f"Syllable {syllable}")
				output += syllable
				next_syllable_index += 1

				sustained_entity = REST
				start_of_sustain += duration

	if next_syllable_index < len(parsed_syllables):
		error("There are more syllables than MIDI notes; output might be truncated")
		error("Remaining syllables: " + str(parsed_syllables[next_syllable_index:]))
		error("TODO: This is likely due to the absence of a note off")

	# TODO: warn if the MIDI track ended with a lingering NOTE_ON (I.e. without a corresponding NOTE_OFF)

	output += ']'

	# Let's write the output file now
	if not os.path.exists(OUTPUT_DIRECTORY):
		os.makedirs(OUTPUT_DIRECTORY)
	output_path = os.path.join(OUTPUT_DIRECTORY, OUTPUT_FILENAME)
	with open(output_path, "w", encoding="utf-8") as output_file:
		output_file.write(output)


main()
