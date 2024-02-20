![image_viewer](site:images/viewer_toolbar.png)

|           |                            |
|: ----------- :| ------------------------------------- |
| ![recall](site:images/viewer_tools/exam-switch-closed.png){ width=200px}     | Exam switcher       |
| ![recall](site:images/viewer_tools/time-scroll.png){ width=200px}     | Time scroll       |
| ![recall](site:images/viewer_tools/aux-switch.png){ width=200px}     | Aux switch       |

## Keyboard controls
<div class="grid" markdown>
<div markdown>
##### Viewports
| Action       | Shortcut                         |
|--------------|----------------------------------|
| Scrolling    | Mouse wheel                      |
| Windowing    | <span class="badge badge-primary">CTRL</span> + left click/drag  |
| Panning      | <span class="badge badge-primary">ALT</span> + left click/drag   |
| Zooming      | <span class="badge badge-primary">ALT</span> + right click/drag  |
| Centering    | <span class="badge badge-primary">SHIFT</span> + left click/drag |
| Move ROI     | <span class="badge badge-primary">SHIFT</span> + left click/drag |
| Fullscreen   | Double click                     |

</div>
<div markdown>
##### Other
| Action        | Shortcut                                          |
| ------------- | ------------------------------------------------- |
| Time          | <span class="badge badge-primary">left</span> / <span class="badge badge-primary">right</span> keys |
| Switch case   | <span class="badge badge-primary">CTRL</span> + <span class="badge badge-primary">left</span> / <span class="badge badge-primary">right</span> keys |
</div>
</div>
## Exam switcher

<div markdown style="overflow: auto;">

![recall](site:images/viewer_tools/exam-switch.png){ align=right width=200px }

This allows switching between exams of the same patient. The :fontawesome-solid-chevron-left: and :fontawesome-solid-chevron-right: buttons switch to the previous and next exam, sorted by time. The center button lets you jump to a particular exam.
</div>

## Time scroll

![Time scroll animation](site:images/viewer_tools/time-scroll-anim.gif){ align=right width=200px }

Select the timepoint to display. While scrolling, a preview of the current viewports will be displayed. When you let go, the full volume will begin to load in. While loading, the tool is disabled.

## Aux switch

This dropdown behavior depends on the type of case you're viewing. It can either switch to an alternate volume to display in the main three viewports (eg, a subtraction volume), or it can pick a volume to display in the auxiliary viewport on the bottom left (eg a heatmap). 

## Toolbar

<div class="grid menu-btns" markdown>

| Tool          | Description                           |
|: ----------- :| ------------------------------------- |
| :fontawesome-solid-ellipsis-vertical:     | Extras       |
| :fontawesome-solid-location-crosshairs: | Reset viewers |
| :fontawesome-solid-lock: | Toggle free MPR rotation |
| :fontawesome-regular-circle: | Add elliptical ROI |
| :fontawesome-solid-plus:    | Add probe annotation |
| :fontawesome-solid-location-dot:    | Select annotation |
| :fontawesome-solid-pencil:    | Rename annotation |

| Tool          | Description                           |
|: ----------- :| ------------------------------------- |
| :fontawesome-solid-copy:     | Duplicate annotation |
| <span class="twemoji"><svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" class="bi bi-symmetry-vertical" viewBox="0 0 16 16"><path d="M7 2.5a.5.5 0 0 0-.939-.24l-6 11A.5.5 0 0 0 .5 14h6a.5.5 0 0 0 .5-.5v-11zm2.376-.484a.5.5 0 0 1 .563.245l6 11A.5.5 0 0 1 15.5 14h-6a.5.5 0 0 1-.5-.5v-11a.5.5 0 0 1 .376-.484zM10 4.46V13h4.658L10 4.46z"></path></svg>     | Flip annotation |
| :fontawesome-solid-trash: | Delete annotation |
| :fontawesome-solid-floppy-disk:     | Save session |
| <span class="twemoji"><svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 512 512"><path d="M504 255.5c.3 136.6-111.2 248.4-247.8 248.5-59 0-113.2-20.5-155.8-54.9-11.1-8.9-11.9-25.5-1.8-35.6l11.3-11.3c8.6-8.6 22.4-9.6 31.9-2C173.1 425.1 212.8 440 256 440c101.7 0 184-82.3 184-184 0-101.7-82.3-184-184-184-48.8 0-93.1 19-126.1 49.9l50.8 50.8c10.1 10.1 2.9 27.3-11.3 27.3H24c-8.8 0-16-7.2-16-16V38.6c0-14.3 17.2-21.4 27.3-11.3l49.4 49.4C129.2 34.1 189.6 8 256 8c136.8 0 247.7 110.8 248 247.5zm-180.9 78.8l9.8-12.6c8.1-10.5 6.3-25.5-4.2-33.7L288 256.3V152c0-13.3-10.7-24-24-24h-16c-13.3 0-24 10.7-24 24v135.7l65.4 50.9c10.5 8.1 25.5 6.3 33.7-4.2z"/></svg></span> | Load session |
| :fontawesome-solid-magnifying-glass-minus: | Reset view |
| :fontawesome-solid-camera: | Create Finding |
</div>

### :fontawesome-solid-ellipsis-vertical: Extras
<div markdown style="overflow: auto;">

![Extras dropdown](site:images/viewer_tools/extras-menu.png){ align=right style=clear:left;}

This dropdown menu contains a handful of extra tools. They are ordinarily only accessible to staff.
#### :fontawesome-solid-arrow-rotate-left: :fontawesome-solid-arrow-rotate-right: Rotate
These will rotate a case in the Axial plane *in place* by 90 degrees. This can be used to fix cases that were reconstructed with the wrong orientation.

#### :fontawesome-solid-gear: Reprocess
Duplicates this case and initiates processing on the new case. This can be used to complete processing on a case that needed to be rotated.

</div>


### :fontawesome-solid-location-crosshairs: Reset viewers
Reset the viewers back to the center of the volume.

### :fontawesome-solid-lock: Toggle free MPR rotation
Clicking on this unlocks the crosshairs to enable free rotation of the volume. Click again to disable rotation and return to in-plane views. While this is turned on, several tools are disabled:

- Timepoint slider
- Annotation adding
### :fontawesome-regular-circle: Add elliptical ROI, :fontawesome-solid-plus: Add probe annotation
These both toggle annotation tools. When either is turned on, click (and with ellipses, drag) to create new annotations. 
### :fontawesome-solid-location-dot: Find annotation

<div markdown style="overflow: auto;">

![recall](site:images/viewer_tools/roi-menu.png){ align=right style=clear:left;}

This button displays a list of annotations. Click on an annotation to select and scroll a viewport to display it.

</div>

<div markdown class="grid bordergrid">

### :fontawesome-solid-pencil: Rename annotation
Give the selected annotation a more descriptive name. 


### :fontawesome-solid-copy: Duplicate annotation
Duplicates the selected annotation in-place. Drag the new annotation to move it to a new location.

<h3><span class="twemoji"><svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="currentColor" class="bi bi-symmetry-vertical" viewBox="0 0 16 16"><path d="M7 2.5a.5.5 0 0 0-.939-.24l-6 11A.5.5 0 0 0 .5 14h6a.5.5 0 0 0 .5-.5v-11zm2.376-.484a.5.5 0 0 1 .563.245l6 11A.5.5 0 0 1 15.5 14h-6a.5.5 0 0 1-.5-.5v-11a.5.5 0 0 1 .376-.484zM10 4.46V13h4.658L10 4.46z"></path></svg></span> Flip annotation</h3>

Flips the annotation across the sagittal plane. 
### :fontawesome-solid-trash: Delete annotation
Deletes an annotation.

### :fontawesome-solid-floppy-disk: Save session
Saves the current annotations.
</div>

<h3><span class="twemoji"><svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 512 512"><path d="M504 255.5c.3 136.6-111.2 248.4-247.8 248.5-59 0-113.2-20.5-155.8-54.9-11.1-8.9-11.9-25.5-1.8-35.6l11.3-11.3c8.6-8.6 22.4-9.6 31.9-2C173.1 425.1 212.8 440 256 440c101.7 0 184-82.3 184-184 0-101.7-82.3-184-184-184-48.8 0-93.1 19-126.1 49.9l50.8 50.8c10.1 10.1 2.9 27.3-11.3 27.3H24c-8.8 0-16-7.2-16-16V38.6c0-14.3 17.2-21.4 27.3-11.3l49.4 49.4C129.2 34.1 189.6 8 256 8c136.8 0 247.7 110.8 248 247.5zm-180.9 78.8l9.8-12.6c8.1-10.5 6.3-25.5-4.2-33.7L288 256.3V152c0-13.3-10.7-24-24-24h-16c-13.3 0-24 10.7-24 24v135.7l65.4 50.9c10.5 8.1 25.5 6.3 33.7-4.2z"/></svg></span> Load session</h3>

<div markdown style="overflow: auto;">

![recall](site:images/viewer_tools/session-menu.png){ align=right }

This opens a menu to either switch to a different session, or create a new one. Each session has its own set of annotations on a particular case.

</div>

<div markdown class="grid bordergrid">

### :fontawesome-solid-magnifying-glass-minus: Reset view 
Resets the pan and zoom on the viewport

### :fontawesome-solid-camera: Create Finding 
Take a screenshot of the viewport and store as a finding
</div>

---
<div markdown style="overflow: auto;">
## Findings
![findings](site:images/viewer_tools/findings.png){ align=right }

Findings are displayed along the right hand side. Click on a finding to open a full-page viewer. 

#### :fontawesome-solid-location-dot: Locate finding
Moves the relevant viewport to the same slice as the finding.
#### :fontawesome-solid-pencil: Edit finding
Add a description to the finding.
#### :fontawesome-solid-trash: Delete finding
Delete the finding permanently.
#### :fontawesome-solid-paper-plane: Send
Send the finding as a DICOM Secondary Capture to the configured destination server

</div>
---
## Charts
![findings](site:images/viewer_tools/chart.png)
The chart graphs intensity or average intensity over time. The vertical line indicates the current time point displayed in the volume viewports. Using the upper-right dropdown box, you can switch between displaying the median, mean, or ptp (the difference between the brightest and darkest pixel) for ROIs. The other dropdown allows "zeroed" or "normalized" display: 

- **zeroed**: For each annotation, subtract the value at the first timepoint from the rest of the values. This shifts all of the traces up or down to start at 0.
- **normalized**: Rescale each trace vertically so its lowest value is 0 and highest value is 1.

#### :fontawesome-solid-download:{ class="menu-btns twemoji"} Download CSV: Downloads a CSV file containing the data displayed.
#### :fontawesome-solid-camera:{ class="menu-btns twemoji"} Create Finding: Create a finding from this chart.