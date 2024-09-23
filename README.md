# MIDI2DECTalk

Use this program to produce .dec or .spk files for DECTalk compatible technology to sing.
It takes two input files:
1. A MIDI file for melody
2. A plain text file for lyrics

The output file will contain the lyrics translated to DECTalk phonemes, both synchronized and pitched in accordance with the MIDI file.

# Setup

1\. Clone or download this repository to your hard drive.
To download this repository from GitHub, go to Code > Download ZIP, then extract the ZIP file.

2\. Download and install Python 3:
https://www.python.org/downloads/

Windows: after installation, it's recommended to add Python to your PATH environment variable:
https://www.geeksforgeeks.org/how-to-add-python-to-windows-path/

3\. Optional, but recommended: Once python is installed, create a virtual environment.
When a virtual environment is activated, the python dependencies you install are local to the project you're working against. This prevents dependency conflicts if your system already uses python.
Details: [venv](https://docs.python.org/3/library/venv.html)

For instance, on Linux / Mac:
```
cd /path/to/extracted/MIDI2DECTalk
python -m venv .
```

Then activate the project before you install any dependencies, or before running the project:
```
source ./bin/activate
```
When you're finished installing dependencies / running the project, and you wish to return to a normal command line, just type:
deactivate

See the above link for Windows instructions.

We're about to install dependencies, so go ahead and activate the virtual environment now.

4\. Use Python's pip tool to install the MIDIFile module from the command line:
```
pip install MIDIFile
```

5\. Download and setup eSpeak:
http://espeak.sourceforge.net/download.html

6\. Download [lexconvert.py](https://github.com/ssb22/lexconvert/raw/master/lexconvert.py) ([documentation](https://ssb22.user.srcf.net/gradint/lexconvert.html)).
Move it into the same directory as this project (E.g. into the MIDI2DECTalk directory created when you extracted the zip file).


# Usage

In the input directory, produce:
1. A plain text file called Lyrics.txt containing some lyrics.
2. A MIDI file containing a single track, with one note per vowel phoneme in the lyrics.

On the command line, if using a virtual environment (recommended), activate it. Then run MIDI2DECTalk:
```
python MIDI2DECTalk.py
```

You will be prompted for the tempo, and then it will generate output/Output.spk


# Configuration

In MIDI2DECTalk.py, review the CONFIGURATION section, and edit as necessary.

# Disclaimer

I do not own any DECTalk technology (I'm just a music & technology geek!). A friend exposed the difficulties of creating .spk files manually and requested this program; the problem piqued my interest. Initial development was completed without a test environment. If you encounter any issues, please report them.

# Testing

The following environment can be used for testing:
https://tts.cyzon.us/ (https://github.com/calzoneman/aeiou)

# Questions / Suggestions / Issues

Please send an email to brianbaillargeon@gmail.com for any questions / suggestions. If you encounter an issue, send the MIDI file, lyrics, and a description of the problem, and I'll do my best to address it. Pull requests are welcome.
