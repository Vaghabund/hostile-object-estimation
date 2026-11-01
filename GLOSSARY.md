# Hostile Object Estimation

A hallway art piece. A camera watches a corridor, finds the face of someone walking past, reads how much they are frowning, and shows the most hostile moment on an e-ink display.

## Language

### The e-ink display

**Display**:
The physical e-ink screen.
_Avoid_: panel, screen

**Picture**:
The whole composed image shown on the display: the portrait on the left and the reading on the right.
_Avoid_: panel, render, display image

**Portrait**:
The face crop on the left of the picture.
_Avoid_: photo, face image

**Reading**:
The right-hand area of the picture: the hostility percentage, its label and its bar.
_Avoid_: panel, stats

### Walk-pasts

**Burst**:
One person's walk past the camera: from the first whole face seen until no face or movement has been seen for a set quiet time. A burst has one graded face.
_Avoid_: visit, walk-by, session

**Burst window**:
The short time after a burst's first whole face during which faces are compared for sharpness.

**Graded face**:
The sharpest whole face seen during a burst's window. Its hostility is the only one read for that burst.
_Avoid_: best frame, first face, peak, capture

### Hostility

**Hostility**:
How much a graded face is frowning, from 0 to 1, shown as a percentage.
_Avoid_: anger, score, peak

**Mood**:
The average hostility of every burst's graded face in the last 24 hours, whether or not its picture reached the display.
_Avoid_: average, barometer value

### Seeing a face

**Motion gate**:
The cheap always-on check that something in the corridor is moving. The face model only runs while it is open.

**Sharpness**:
How in-focus a face is in a frame. It falls with blur and with dim light. A face below the minimum sharpness is never a candidate for grading.

**Whole face**:
A face fully inside the camera's view. Faces cut off by the frame edge are ignored, so the display never shows half a face.

**Face marks**:
The eyes, brows, nose, mouth and face outline drawn over the portrait.

### The mood and the archive

**Barometer**:
The scale above the date in the reading that shows the mood, from calm to hostile.

**Shown picture**:
A picture that was put on the display. Kept for the 24-hour window, then deleted.
_Avoid_: saved picture, history

**Review**:
The Telegram `/review` answer: the most hostile shown pictures of the last 24 hours with the mood and an hourly mood chart.

**Snap**:
The Telegram `/snap` answer: the camera's view right now, as a plain photo. Never stored.
