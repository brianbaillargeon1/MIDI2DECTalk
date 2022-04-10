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

3\. Once python is installed, use Python's pip tool to install the MIDIFile module from the command line:
```
pip3 install MIDIFile
```
Note: if you have py-midi installed, it can conflict. If you encounter issues, remove py-midi with:
```
pip3 uninstall py-midi
```

4\. Download and setup eSpeak:
http://espeak.sourceforge.net/download.html

5\. Download [lexconvert.py](https://github.com/ssb22/lexconvert/raw/master/lexconvert.py) ([documentation](https://ssb22.user.srcf.net/gradint/lexconvert.html)).
Move it into the same directory as this project (E.g. into the MIDI2DECTalk directory created when you extracted the zip file).


# Usage

In the input directory, produce:
1. A plain text file called Lyrics.txt containing some lyrics.
2. A MIDI file containing a single track, with one note per vowel phoneme in the lyrics.

On the command line, run MIDI2DECTalk:
```
python3 MIDI2DECTalk.py
```

You will be prompted for the tempo, and then it will generate output/Output.spk


# Configuration

In MIDI2DECTalk.py, review the CONFIGURATION section, and edit as necessary.

# Disclaimer

I do not own any DECTalk technology (I'm just a music & technology geek!). A friend exposed the difficulties of creating .spk files manually and requested this program; the problem piqued my interest. If you encounter any issues, please report them.

# Questions / Suggestions / Issues

Please send an email to brianbaillargeon@gmail.com for any questions / suggestions. If you encounter an issue, send the MIDI file, lyrics, and a description of the problem, and I'll do my best to address it. Pull requests are welcome.
