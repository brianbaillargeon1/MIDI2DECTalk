#!/usr/bin/env python

# ==== DEPENDENCIES ====

# https://pypi.org/project/MIDIFile/
# Can be obtained via `pip3 install MIDIFile`

# lexconvert.py and eSpeak, see README.md

import math
import MIDI
import sys
import os


# ==== CONFIGURATION ====

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
CONSONANT_DURATIONS = {}
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

# The Python executable to invoke lexconvert.py.
# Default: the executable that invoked this program.
PYTHON3 = sys.executable

# Set to True to print debug information to STDOUT
DEBUG = False


# ==== CONSTANTS ====

# Categorization of "dectalk" dictionary in lexconvert.py into vowels and consonants.
# The order is important to prevent ambiguity. I.e. 'lx' comes before 'l', 'rx' comes before 'r', etc.
# lexconvert.py includes 'ihr', but explains that it parses to 'ih', and 'r'; I have omitted it.
VOWELS = ['aa', 'ae', 'ah', 'ao', 'aw', 'ax', 'ay', 'eh', 'el', 'ey', 'ih', 'ix', 'iy', 'ow', 'oy', 'rr', 'uh', 'uw', 'yx']

CONSONANTS = ['b', 'ch', 'dx', 'dh', 'd', 'f', 'g', 'hx', 'q', 'jh', 'k', 'lx', 'l', 'm', 'nx', 'n', 'p', 'rx', 'r', 'sh', 's', 'tx', 'th', 't', 'v', 'w', 'zh', 'z']

# Phoneme representing silence
REST = '_'

# Values representing types of matches while parsing phonemes:
CATEGORY_VOWEL = 'V'
CATEGORY_CONSONANT = 'C'
CATEGORY_COMMA = ','

# A440 in MIDI: 69, A440 in DECTalk: 34. Their difference: 35
MIDI_DECTALK_PITCH_DELTA = 35

# For identifying the MIDI event types.
UNUSED = -1
NOTE_ON = 144
NOTE_OFF = 128


# ==== FUNCTIONS ====

def debug(message: str):
	if DEBUG:
		print(message)

def info(message: str):
	print(message)

def error(message: str):
	print(message, file=sys.stderr)

def splitMatchAsTuple(phonemes: str, possibleMatches: [str], matchApostrophe: bool) -> (str, str):
	"""
	Checks if phonemes starts with a token in the possibleMatches list
	Params:
	phonemes: an str like 'hxehl'ow, w'rrld'
	possibleMatches: one of the constant lists VOWELS or CONSONANTS
	matchApostrophe: whether or not matching tokens might be prefixed with an apostrophe

	Returns:
	A tuple: (matching phoneme, phoneme list with the match removed)
	E.g. ("hx", "ehl'ow, w'rrld")
	If no possibleMatches match, returns None
	"""

	remainder = phonemes
	matched = False
	match = ''
	if matchApostrophe and phonemes[0] == '\'':
		match = '\''
		remainder = phonemes[1:]
	for token in possibleMatches:
		if remainder.startswith(token):
			matched = True
			match = match + token
			remainder = remainder[len(token):]
			break
	if matched:
		return (match, remainder)
	return None

def categorizePhonemes(phonemes: str) -> [(str, str)]:
	"""
	Parses phonemes, and categorizes them into vowels, constants, and commas
	(commas represent word endings).
	Params:
	phonemes: an str like 'hxehl'ow, w'rrld'

	Returns
	a list of tuples: [(phoneme, category)],
	where the category is one of the constants: CATEGORY_VOWEL, CATEGORY_CONSONANT, or CATEGORY_COMMA
	"""

	toParse = phonemes
	categorizedPhonemes = []
	matchFound = True

	while matchFound and toParse:
		splitAsTuple = splitMatchAsTuple(toParse, VOWELS, True)
		if splitAsTuple:
			categorizedPhonemes.append((splitAsTuple[0], CATEGORY_VOWEL))
			toParse = splitAsTuple[1]
			continue
		splitAsTuple = splitMatchAsTuple(toParse, CONSONANTS, False)
		if splitAsTuple:
			categorizedPhonemes.append((splitAsTuple[0], CATEGORY_CONSONANT))
			toParse = splitAsTuple[1]
			continue
		splitAsTuple = splitMatchAsTuple(toParse, [", "], False)
		if splitAsTuple:
			categorizedPhonemes.append((splitAsTuple[0], CATEGORY_COMMA))
			toParse = splitAsTuple[1]
			continue
		matchFound = False
	if not matchFound:
		error("Error parsing phonemes; could not find a match at the start of: " + toParse)
	return categorizedPhonemes

def parsePhonemes(phonemes: str) -> [[str]]:
	"""
	Parses the param 'phonemes', an str like 'hxehl'ow, w'rrld',
	and returns a nested list that groups these phonemes into syllables.
	We define a syllable as a group of phonemes containing exactly one vowel.
	For example, with input hxehl'ow, w'rrld, we would return:
	[['hx', 'eh'], ['l', '\'ow'], ['w', '\'rr', 'l', 'd']]
	"""

	# Return value (outer list)
	parsed = []
	# Current syllable's phonemes (inner list)
	syllablePhonemes = []

	categorizedPhonemes = categorizePhonemes(phonemes)
	debug("Token List:\n" + str(categorizedPhonemes))

	# Iterate over the categorizedPhonemes and buffer them into syllablePhonemes.
	# We've completed a syllable when we've reached one of the following conditions:
	# 1) we've hit a comma (I.e. the end of a word)
	# 2) syllablePhonemes contains a vowel, and we're about to read a second vowel
	# 3) the end of categorizedPhonemes has been reached

	consonantsBetweenVowels = 0
	vowelPresent = False
	for categorizedPhoneme in categorizedPhonemes:
		if categorizedPhoneme[1] == CATEGORY_COMMA:
			# Word endings are syllable endings
			if (syllablePhonemes):
				parsed.append(syllablePhonemes)
			consonantsBetweenVowels = 0
			vowelPresent = False
			syllablePhonemes = []

		elif categorizedPhoneme[1] == CATEGORY_CONSONANT:
			syllablePhonemes.append(categorizedPhoneme)
			consonantsBetweenVowels+=1

		elif categorizedPhoneme[1] == CATEGORY_VOWEL:
			if vowelPresent:
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

				if consonantsBetweenVowels == 0:
					# Two consecutive vowels, start a new syllable 
					parsed.append(syllablePhonemes)
					syllablePhonemes = []
				elif consonantsBetweenVowels == 1:
					# A single consonant between vowels: [hx, eh] *l* [ow, ...]"
					# Individual consonants tend to start syllables: [hx, eh], [l, oh, ...]
					parsed.append(syllablePhonemes[:-1])
					syllablePhonemes = [syllablePhonemes[-1]]
				else:
					# Suitable for the majority of words (cases like "firstly", "helpful"):
					# Put ceil(consonants/2) on the first syllable, and floor(consonants/2) on the second syllable
					numSecondWordConsonants = math.floor(consonantsBetweenVowels/2)
					secondWordConsonants = syllablePhonemes[-numSecondWordConsonants:]
					parsed.append(syllablePhonemes[:-numSecondWordConsonants])
					syllablePhonemes = secondWordConsonants

			syllablePhonemes.append(categorizedPhoneme)
			vowelPresent = True
			consonantsBetweenVowels = 0

	if syllablePhonemes:
		parsed.append(syllablePhonemes)

	debug("Parsed:\n" + str(parsed))

	return parsed

def getEventType(event) -> int:
	"""
	Gets a MIDI event's effective event type.
	NOTE_ON with velocity 0 returns NOTE_OFF.
	Returns NOTE_ON, NOTE_OFF, or UNUSED
	"""
	if event.header == NOTE_ON and event.message.velocity == 0:
		return NOTE_OFF
	elif event.header in (NOTE_OFF, NOTE_ON):
		return event.header
	return UNUSED

def getMidiPitch(note: MIDI.Events.messages.notes.Note) -> int:
	""" Takes a Note instance and gets its MIDI pitch number (E.g. A440 returns 69) """
	# Consider A440:
	# It is represented as 'a5'; its MIDI pitch is #69
	# 5 octaves * 12 pitches / octave + 9 pitches = 69 pitches
	notes = MIDI.Events.messages.notes.Note.notes
	return note.octave*12 + notes.index(note.note)

def getDECTalkPitch(note: MIDI.Events.messages.notes.Note) -> int:
	""" Takes a Note instance and gets its DECTalk pitch number (E.g. A440 returns 34) """
	return getMidiPitch(note) - MIDI_DECTALK_PITCH_DELTA

def getEventTimeMillis(event: MIDI.Events.event.Event, tempo, ticksPerBeat, firstNoteTicks) -> float:
	"""
	Takes a MIDI event and returns its time in milliseconds
	event: MIDI Event
	tempo: beats per minute
	ticksPerBeat: how many MIDI ticks per beat
	firstNoteTicks: how many MIDI ticks elapsed before the first note
	"""
	timeInTicks = event.time
	if firstNoteTicks:
		timeInTicks -= firstNoteTicks
	# beats = ticks / (ticks / beats)
	beatsElapsed = timeInTicks / ticksPerBeat
	# milliseconds = beats / (beats / minute) * (60 seconds / minute) * (1000 ms / second)
	return 60000 * beatsElapsed / tempo

def getConvertedPhoneme(phoneme: str) -> str:
	""" Translates phonemes produced by lexconvert.py to phonemes supported by the targeted technology """
	if phoneme in PHONEME_CONVERSION:
		return PHONEME_CONVERSION[phoneme]
	return phoneme

def getConsonantDuration(consonant: str) -> int:
	"""
	Checks for a mapping for this consonant in CONSONANT_DURATIONS.
	Returns the default consonant duration if no mapping is specified.
	"""
	key = consonant
	if key in CONSONANT_DURATIONS:
		return CONSONANT_DURATIONS[key]
	return DEFAULT_CONSONANT_DURATION

def translateSyllableToDECTalk(syllable: [(str, str)], note: MIDI.Events.messages.notes.Note, duration: int) -> str:
	"""
	Translates a syllable into the output format.
	Example syllable: [('w', 'c'), ('\'rr', 'v'), ('l', 'c'), ('d', 'c')]
	If the note is A440, and the duration is 500ms; this would be returned as:
	w<90>'rr<230,34>ll<90>d<90>
	"""

	outputText = ""

	totalConsonantDuration = 0
	for categorizedPhoneme in syllable:
		if categorizedPhoneme[1] == CATEGORY_CONSONANT:
			convertedPhoneme = getConvertedPhoneme(categorizedPhoneme[0])
			totalConsonantDuration += getConsonantDuration(convertedPhoneme)

	vowelDuration = duration - totalConsonantDuration
	if vowelDuration < 0:
		error("Could not fit all the phonemes within " + str(duration) + " milliseconds.")
		error("Consider reducing DEFAULT_CONSONANT_DURATION, or ensure your MIDI notes are sufficiently long.")
		#TODO: Call a cleanup method to close all the files
		exit()

	for categorizedPhoneme in syllable:
		convertedPhoneme = getConvertedPhoneme(categorizedPhoneme[0])
		if categorizedPhoneme[1] == CATEGORY_CONSONANT:
			consonantDuration = getConsonantDuration(convertedPhoneme)
			outputText += '{}<{}>'.format(convertedPhoneme, str(int(consonantDuration)))
		elif categorizedPhoneme[1] == CATEGORY_VOWEL:
			outputText += '{}<{},{}>'.format(convertedPhoneme, str(int(vowelDuration)), str(getDECTalkPitch(note)))

	return outputText

def getDECTalkRest(duration: int) -> str:
	""" Gets a rest for the specified duration in the output format """
	return REST + '<' + str(int(duration)) + '>'


# ==== MAIN PROGRAM ====

# Get the BPM
tempoStr = input("What's the BPM? ")
# Precise sync'ing may be needed. Support decimals - use float.
tempo = float(tempoStr)
# TODO: add support to read tempo meta messages.


# Convert lyrics into DECTalk phonemes:
# TODO: Exception handling
lyricsFilePath = os.path.join(INPUT_DIRECTORY, LYRICS_INPUT_FILENAME)
textFile = open(lyricsFilePath, 'r')
lyrics = textFile.read()
textFile.close()

from subprocess import Popen, PIPE
# TODO: Exception handling
process = Popen([PYTHON3, "lexconvert.py", "--phones", "dectalk", lyrics], stdout=PIPE)
(lexConvertOutput, err) = process.communicate()
exit_code = process.wait()

# Clean up output, and unify the delimiters between words as commas
phonemes = lexConvertOutput.decode('UTF-8')
phonemes = phonemes.replace("[:phoneme on]\n[", "", 1)
phonemes = phonemes.replace("] [", ", ")
phonemes = phonemes.replace("]\n[", ", ")
phonemes = phonemes.replace("]", "")
phonemes = phonemes.replace("\n", "")
debug("Phonemes:\n" + str(phonemes))


# Convert the phonemes into a list of syllables
parsedSyllables = parsePhonemes(phonemes)


# Read the MIDI file, and parse the MIDI track whose events will be iterated
# TODO: Exception handling
midiFilePath = os.path.join(INPUT_DIRECTORY, MIDI_INPUT_FILE)
midiIn = MIDI.MIDIFile(midiFilePath)
midiIn.parse()

# Ticks per beat of the BPM
ticksPerBeat = float(midiIn.division)
debug("Ticks per beat: " + str(ticksPerBeat))

if TRACK_NUMBER == 0 and len(midiIn) > 1:
	info("Multiple tracks detected; only the first track will be used")
elif TRACK_NUMBER >= len(midiIn):
	error("The configured TRACK_NUMBER exceeds the highest track number in the MIDI file")
	# TODO: cleanup
	exit()

track = midiIn[TRACK_NUMBER]
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
nextSyllableIndex = 0

# It's common for the first note in a MIDI file to be delayed by a number of ticks.
# We'd rather not start the output file with a leading rest.
# Once the first note's time is detected, all timing will be shifted earlier this many ticks.
# This way, the output begins immediately.
firstNoteTicks = None

# As we iterate through MIDI events, this is the entity that has last started sustaining.
# Its value can be REST, or a MIDI.Events.messages.notes.Note
sustainedEntity = None
# The time in milliseconds that sustainedEntity begins sustaining in the output file.
# This is the sum of the durations that have been output so far.
startOfSustain = 0

for event in track:
	eventType = getEventType(event)

	# TODO: handle if event type is either NOTE_ON or NOTE_OFF, but there are no more syllables (I.e. add some 'ooh yeahs')

	if eventType == NOTE_ON:
		if not firstNoteTicks:
			firstNoteTicks = event.time

		eventTimeMillis = getEventTimeMillis(event, tempo, ticksPerBeat, firstNoteTicks)

		if sustainedEntity:
			# Output the sustained entity, then start sustaining the new one
			duration = round(eventTimeMillis - startOfSustain, 0)
			if sustainedEntity == REST:
				output += getDECTalkRest(duration)
			else:
				output += translateSyllableToDECTalk(parsedSyllables[nextSyllableIndex], sustainedEntity, duration)
				nextSyllableIndex += 1
			startOfSustain += duration

		sustainedEntity = event.message.note
	elif eventType == NOTE_OFF:
		if sustainedEntity.note == event.message.note.note and sustainedEntity.octave == event.message.note.octave:
			# This NOTE_OFF event ends sustainedEntity. Write the entity, then begin a rest.
			eventTimeMillis = getEventTimeMillis(event, tempo, ticksPerBeat, firstNoteTicks)
			duration = round(eventTimeMillis - startOfSustain, 0)
			output += translateSyllableToDECTalk(parsedSyllables[nextSyllableIndex], sustainedEntity, duration)
			nextSyllableIndex += 1

			sustainedEntity = REST
			startOfSustain += duration

# TODO: add handling if there are still more syllables
# TODO: warn if the MIDI track ended with a lingering NOTE_ON (I.e. without a corresponding NOTE_OFF)

output += ']'

# Let's write the output file now
if not os.path.exists(OUTPUT_DIRECTORY):
	os.makedirs(OUTPUT_DIRECTORY)
outputPath = os.path.join(OUTPUT_DIRECTORY, OUTPUT_FILENAME)
outputFile = open(outputPath, "w")
outputFile.write(output)
# TODO: call a cleanup method to close all the files
outputFile.close()

