```
U.S. NATIONAL WEATHER SERVICE
```
# EMWIN QBT Satellite

# Broadcast Protocol

## Draft Version 1.0.

WARNING
THIS IS A DRAFT SPECIFICATION DOCUMENT UNDER DEVELOPMENT BY THE US NATIONAL WEATHER
SERVICE. IT HAS NOT BEEN VERIFIED FOR ACCURACY OR FOR COMPATIBILTY WITH ANY EXISTING
SYSTEMS OR SERVICES. THE USE OF THIS INFORMATION BY ANY PARTY FOR ANY PURPOSE IS AT THEIR
OWN RISK. THE GOVERNMENT MAY NOT BE HELD LIABLE FOR ANY DIRECT OR CONSEQUENTIAL
DAMAGES ARISING FROM INFORMATION CONTAINED IN THIS DOCUMENT.


## Document Control

```
Version
Number
```
```
Version Description Author(s) Date Completed
```
```
V 1.0.
Draft
```
```
Initial Version of Draft Document * Robert Gillespie 5/12/
```
```
V 1.0.
Draft
```
```
3.b.(5) - correct file date/time stamp
4.a. & 5 – corrected errors Header
```
```
Robert Gillespie 12/1/
```
```
V 1.0.3 3.b – added out-of-sequence packet error Robert Gillespie 12/2/
```
* A portion of the content of this document was provided by Danny Lloyd, Weather Message Software,
LLC

```
WARNING
THIS IS A DRAFT SPECIFICATION DOCUMENT UNDER DEVELOPMENT BY THE US
NATIONAL WEATHER SERVICE. IT HAS NOT BEEN VERIFIED FOR ACCURACY AND
COMPATIBILTY WITH ALL EXISTING EMWIN SYSTEMS OR SERVICES. THE USE OF THIS
INFORMATION BY ANY PARTY FOR ANY PURPOSE IS AT THEIR OWN RISK. THE
GOVERNMENT MAY NOT BE HELD LIABLE FOR ANY DIRECT OR CONSEQUENTIAL
DAMAGES ARISING FROM INFORMATION CONTAINED IN THIS DOCUMENT.
```

## EMWIN QBT Satellite Broadcast Protocol

### Draft Version 1.0. 3

1. Introduction.

a. This document describes the Quick Block Transfer (QBT) protocol used by the U.S. National
Weather Service (NWS) for the transmission of files over the National Environmental Satellite,
Data, and Information Service (NESDIS) Geostationary Operational Environmental Satellites
(GOES) 13, 14 and 15 [the GOES N/O/P satellite series]. This protocol is unique to the NWS
Emergency Managers Weather Information Network (EMWIN).

b. The EMWIN satellite broadcast data stream consists of both text and binary files. Prior to
broadcast, each file is divided into a sequence of 1024 byte segments which are encapsulated in
1116 byte QBT packets for transmission. The individual or series of QBT packets for a specific
file are numbered sequentially from 1 to N. Upon receipt of the packets from the satellite
broadcast, the receiving system software will reconstitute the files from the QBT packets.

c. Dividing files into smaller packets allows EMWIN to expedite the transmission of higher
priority files ahead of lower priority files. This is accomplished by interrupting the transmission
of lower priority file packets, and allowing the higher priority file packets to be transmitted.
After the higher priority file packets have been transmitted, the transmission if the lower priority
file packets resumes.

d. The EMWIN data stream on the GOES-13/14/15 satellites is transmitted at 19,200 kbps, and
is not encrypted.

2. EMWIN Transmission Performance.

a. All EMWIN files are assigned a numeric priority. The priority helps determine the order in
which files are sent according to the following guidelines:

```
(1) Higher priority (file) packets are transmitted ahead of lower priority (file) packets.
```
(2) The file’s packets are transmitted in ascending packet number order, beginning with
packet number 1.

(3) At any given priority level, packets in a queue will be transmitted in “First In, First Out”
(FIFO) order.

b. If the receiving system software detects out-of-sequence, missing, incomplete, or mal-formed
packets, the product and its associated sequence of QBT packets may be reported as “bad” or
“corrupt” and discarded.

c. The EMWIN satellite broadcast is receive-only, therefore the receiver has no means of
notifying the transmitter of any packet loss or errors, nor may it request retransmission of
individual packets.


```
EMWIN QBT Satellite Broadcast Protocol draft v1.0.
```
d. Each high priority file is transmitted twice to improve the likelihood of successfully receiving
the file. The file retransmission is scheduled to commence no sooner than 5 seconds after the file
is first transmitted, but may take longer, depending on the number of existing packets ahead of it
in the transmission queue.

3. QBT Protocol - Each QBT packet is 1116 bytes in length. The QBT packet is composed of
the following fields:

a. Prefix – 6 bytes. Position 1-6, 6 bytes of [ASCII 0 (null)]

b. Header – 80 bytes consisting of the following elements

```
(1) Product Filename (PF). Position 7-21, literal "/PF" followed by an 8-character
filename, a period, and a three character file extension. Valid file extensions are:
```
```
(a) gif Graphics Interchange Format
(b) jpg shorter extension for JPEG which stands for Joint Photographic Experts
Group.
(c) png Portable Network Graphics file format
(d) txt alpha numeric text format
(e) zis ZIP compressed file format
```
```
(2) Packet Number (PN). Position 22-30, literal "/PN" followed by a left justified
number, 1 to 6-bytes in length, identifying the packet’s sequence number in the range of
1 to N. Right pad with [ASCII 32 (SP)] to fill out to byte position 30.
```
```
(3) Packets Total (PT). Position 31-39, literal "/PT" followed by a left justified number,
1 to 6-bytes in length, identifying the total number of packets N being sent for this file.
Right pad with [ASCII 32 (SP)] to fill out to byte position 39.
```
```
(4) Computed Sum (CS). Position 40-49, literal "/CS" followed by a 7-byte, left justified
number identifying the sum of all unsigned byte decimal values in the 1024-byte data
block portion of the packet (Section 3.c.). Right pad with [ASCII 32 (SP)] to fill out to
byte position 49.
```
```
All bytes in data block are unsigned (non-negative) values. The individual byte value
range is 0 to 255. The resulting maximum value of the computed sum is: 1024 bytes x
255 (max value/byte) = 261120. The sum of all byte decimal values is unsigned.
```

```
EMWIN QBT Satellite Broadcast Protocol draft v1.0.
```
```
(a) Text File example sending “AcB” in the data block portion of the packet. The
computed sum = 230:
```
```
Data Block
Byte No.
```
```
Text File:
ASCII
Characters
```
```
Decimal Unsigned
Byte-bits
```
```
Hex Counted
Decimal
Value ..
87 A 65 01000001 41 65
88 c 99 01100011 63 99
89 B 66 01000010 42 66
90 (null) 0 00000000 00 0
: : : : : :
1110 (null) 0 00000000 00 0
```
* COMPUTED SUM * 230

```
(b) Binary File example sending hexidecimal bytes “FF B4 42” in the data portion of
the packet. The computed sum = 501:
```
```
Data Block
Byte No.
```
```
Text File:
ASCII
Characters
```
```
Decimal Unsigned
Byte-bits
```
```
Binary
File
(Hex)
```
```
Counted
Decimal
Value ..
87 n/a 255 11111111 FF 255
88 n/a 180 10110100 B4 180
89 B 66 01000010 42 66
90 (null) 0 00000000 00 0
: : : : : :
1110 (null) 0 00000000 00 0
```
* COMPUTED SUM * 501

(5) File Date-Time (FD). Position 50-84, literal "/FD" followed by the date/time stamp
of the file from which the data was received; in the left justified format of:
MM/DD/YYYY[ASCII 32 (SP)]hh:mm:ss[ASCII 32 (SP)]AM or PM in universal
coordinated time (UTC).

```
(a) Sequential Fields and Values: Month (MM) = 1- 12; Day (DD) = 1-31; Year
(YYYY) = 20##; hour (hh) = 1-12; minute (mm) = 00-59; seconds (ss) = 00 -
```
```
(b) The field for Month (MM), Day (DD) and hour (hh) will use a single integer digit
when the value is less than 10. Leading zeros are not used. For example, January 2,
2016 is formatted as 1/2/
```
```
(c) Padding - append [ASCII 32 (SP)] to fill the “/FD” field to byte position 84.
```
(6) Separator. Position 85-86 [ASCII 13 (CR)] and [ASCII 10 (LF)].


```
EMWIN QBT Satellite Broadcast Protocol draft v1.0.
```
c. Data Block - Position 87-1110, 1024-byte block; left justified sequence of bytes from the text
or binary file. If the number of bytes from the text or binary file is less than 1024 bytes, the
[ASCII 0 (null)] byte is appended to fill, so that each packet's data block is always 1024 bytes
long.

d. Suffix - Position 1111-1116, 6 bytes of [ASCII 0 (null)]

4. Example.

a. Header - an example of the 80-byte packet header:

```
/PFZFPSFOCA.TXT/PN3(sp)(sp)(sp)(sp)(sp)/PT5(sp)(sp)(sp)(sp)(sp)/CS63366(sp)(sp)
/FD5/19/2016(sp)5:24:26(sp)PM(sp)(sp)(sp)(sp)(sp)(sp)(sp)(sp)(sp)(sp)(cr)(lf)
```
b. The content of the NWS weather products placed into the 1024-byte data blocks, may be
alphanumeric text or binary ( hexadecimal) representation as prescribed in WMO-No. 386,
Manual on the Global Telecommunication System, Annex III to the WMO Technical
Regulations, 2015 edition. The products are not encrypted, but will be compressed if their size
exceeds 5kB. Interpretation of the content of the products is up to the receiver's software.
Compressed products have a file name that ends with .ZIS and uses standard ZIP file
compression.

5. QBT Protocol Position Reference Diagram – with field separators and sample data.

6 x00 /PFZFPSFOCA.TXT /PN3 /PT5 /CS
1 7 22 31 40

/FD5/19/2016 5:24:26 PM x0d x0a 1024 data bytes 6 x
50 85 87 1111


