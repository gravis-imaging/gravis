# Case Types

GRAVIS supports two case types currently. They each have different processing pipelines and slightly different viewer UIs. 

## GRASP MRA
GRASP MRA cases have a Maximum Intensity Projection (displayed in the lower left), and a 4D subtraction volume (accessible by switching the dropdown from ORI to SUB). 

![mra viewer](site:images/viewer_tools/viewer-mra.png)

## GRASP Onco
GRASP Onco cases generate a series of heatmaps, displayed in the lower left, and selected by switching the lefthand dropdown. The display next to the heatmap viewport shows the average value of each heatmap for each annotation.

|   |   |
|---|---|
| AUC  | Area under the curve  |
| NORM_WIN | Normalized wash-in |
| NORM_WOUT | Normalised wash-out |
| PEAK     | Peak value |
| WIN      | Wash in |
| WOUT     | Wash out |



![onco viewer](site:images/viewer_tools/viewer-onco.png)

## Series Viewer
The Series Viewer can display GRASP volumes without creating any additional series. 
