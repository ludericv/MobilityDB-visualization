# Visualizing MobilityDB data using QGIS
This document will go over the possible solutions to display MobilityDB data types using the QGIS application.

## QGIS high level description

QGIS data is displayed inside layers. The actual data can be stored in different ways:
- The layer could be linked to a table inside a postgresql database with a postgis extension. In this case, if the table contains a geometry type column (point, linestring, polygon, etc.), the data will be automatically "recognized" by QGIS and displayed.
- The data is stored inside the layer's memory. Data is organized as *features*.

### Features
Features are the way data are represented inside a memory layer. Features have a geometry and attributes. The attributes contain information about the data that isn't displayed (e.g. a name, a time, a number such as an age) but can be used to filter which features should be rendered inside the layer or how they should be rendered (for example changing their size or color).

## Problem description

The goal is to be able to display MobilityDB data using QGIS, for example, moving points on a 2D plane. Since MobilityDB introduces new data types to account for its temporal dimension, it is not possible to simply "link" a temporal geometry column from the database to a QGIS layer. To display such data, we need to transform it into types QGIS recognizes. To do the actual visualization, we can make use of QGIS's temporal controller. This tool allows the creation of animations (an animation frame contains a set of features during a given time range) and introduces a way to filter which features in a layer are shown depending on one or several time attributes. 

## Assumptions

The data set used for the experiments is a table of 100 rows that each contain the information of the trajectory of a single point. Each row is divided into several columns. Several columns contain non-spatial information (e.g. a unique identifier). One column stores the spatio-temporal information of each point (i.e. its trajectory) as a tgeompoint. The goal is to interpolate each point's tgeompoint trajectory for every frame's timestamp of QGIS's temporal controller to create an animation.

## Solutions
### Using the Temporal Controller
Let's first describe how the temporal controller is useful. We can manually set a start time, an end time, the time between each frame (step) and the framerate. What we want to do now is to be able to draw the points from the database whose trajectory intersects (in the temporal dimension) the time range of the current animation frame for any frame. From the current knowledge I have, there is only one way to detect when the temporal controller goes to a new frame : by connecting a slot to the updateTemporalRange() signal. See the following script :
```python
temporalController = iface.mapCanvas().temporalController()

def newFrame(range):
    ### Do something clever here
    
temporalController.updateTemporalRange.connect(newFrame)
```
