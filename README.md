# Visualizing MobilityDB data using QGIS
This document will go over the possible solutions to display MobilityDB data types using the QGIS application.

## QGIS high level description

QGIS data is displayed inside layers. The actual data can be stored in different ways:
- The layer could be linked to a table inside a postgresql database with a postgis extension. In this case, if the table contains a geometry type column (point, linestring, polygon, etc.), the data will be automatically "recognized" by QGIS and displayed.
- The data is stored inside the layer's memory. Data is organized as *features*.

### Features
Features are the way data are represented inside a memory layer. Features have a geometry and attributes. The attributes contain information about the data that isn't displayed (e.g. a name, a time, a number such as an age) but can be used to filter which features should be rendered inside the layer or how they should be rendered (for example changing their size or color). The geometry contains all of the information needed to be able to locate the feature on a map (e.g. its coordinates if the feature is a point).

## Problem description

The goal is to be able to display MobilityDB data using QGIS, for example, moving points on a 2D plane. Since MobilityDB introduces new data types to account for its temporal dimension, it is not possible to simply "link" a temporal geometry column from the database to a QGIS layer. To display such data, we need to transform it into types QGIS recognizes. To do the actual visualization, we can make use of QGIS's temporal controller. This tool allows the creation of animations (an animation frame contains a set of features during a given time range) and introduces a way to filter which features in a layer are shown depending on one or several time attributes. 

## Assumptions

The data set used for the experiments is a table of 100 rows that each contain the information of the trajectory of a single point. Each row is divided into several columns. Several columns contain non-spatial information (e.g. a unique identifier). One column stores the spatio-temporal information of each point (i.e. its trajectory) as a tgeompoint. The goal is to interpolate each point's tgeompoint trajectory for every frame's timestamp of QGIS's temporal controller to create an animation.

## Using the Temporal Controller
Let's first describe how the temporal controller is useful. We can manually set a start time, an end time, the time between each frame (step) and the framerate. What we want to do now is to be able to draw the points from the database whose trajectory intersects (in the temporal dimension) the time range of the current animation frame for any frame. From the current knowledge I have, there is only one way to detect when the temporal controller goes to a new frame : by connecting a slot to the updateTemporalRange() signal. See the following script :
```python
temporalController = iface.mapCanvas().temporalController()

def onNewFrame(range):
    ### Do something clever here
    
temporalController.updateTemporalRange.connect(newFrame)
```
The _onNewFrame_ function is called whenever the temporal controller changes its temporal range, i.e. whenever a new frame needs to be drawn. The range parameter the function receives is the frame's temporal range (begin and end times can be retrieved by calling range.begin() and range.end()). 
The interpolation from a point's trajectory to its location at a single instant (e.g. the beginning, middle, or end of the frame) will need to be done inside this function.

### On-the-fly interpolation
We could do the interpolation every time the _onNewFrame_ function is called. Again, the animation will only be smooth if execution_time < 1/FPS. Here, features need not store an attribute with the time of the interpolation since only features from the current frame are part of the layer (either the features are deleted and created at every frame, or the geometry of a fixed 100 features is changed every tick).
From this we can see two main ways of doing things.

### Buffering frames
We can do the interpolation for a fixed amount of frames, N. If we want the animation to be completely smooth, the execution of interpolation of the points for these N frames needs to be less than the time it takes for the N frames to be rendered (execution_time < N/FPS). For this solution, even though N frames are buffered, only 1 frame of the animation needs to be rendered at any given time. This means that the features generated will need to contain an attribute with the time of the interpolation. The temporal controller can then filter on this attribute to only show the features corresponding to the current frame.



## Experiments
There are now two main questions :
- Should frames be buffered ?
- How should the interpolation be done ? The goal is to make it as efficient as possible since in any case (buffering or not), the execution time needs to be under a certain threshold.

The following experiments attempt to compare different possible solutions

### Experiment 1

There are two main ways to do the interpolation. We can either directly run a query on the database (using the postgisexecuteandloadsql qgis algorithm) or use the mobilitydb python driver (we query the database and get mobilitydb python types on which we can do the interpolation using the driver functions). Let's establish the baseline cost to generate/update features for a single frame using each method.

#### Experiment 1.1
Let's first measure the time it takes to update the geometry of 100 features using the mobilitydb driver.
```python
import time
now = time.time()
canvas = iface.mapCanvas()
temporalController = canvas.temporalController()
currentFrameNumber = temporalController.currentFrameNumber()
features_list = []
interpolation_times = []
feature_times = []

# For every frame, use  mobility driver to retrieve valueAtTimestamp(frameTime) and create a corresponding feature

dtrange = temporalController.dateTimeRangeForFrameNumber(currentFrameNumber+i)
for row in rows:
    now2 = time.time()
    val = row[0].valueAtTimestamp(dtrange.begin().toPyDateTime().replace(tzinfo=row[0].startTimestamp.tzinfo)) # Get interpolation
    interpolation_times.append(time.time()-now2)
    if val: # If interpolation succeeds
        now3 = time.time()
        feat = QgsFeature(vlayer.fields())   # Create feature
        feat.setAttributes([dtrange.end()])  # Set its attributes
        geom = QgsGeometry.fromPointXY(QgsPointXY(val[0],val[1])) # Create geometry from valueAtTimestamp
        feat.setGeometry(geom) # Set its geometry
        feature_times.append(time.time()-now3)
        features_list.append(feat)
now4 = time.time()
vlayer.startEditing()
vlayer.addFeatures(features_list) # Add list of features to vlayer
vlayer.commitChanges()
iface.vectorLayerTools().stopEditing(vlayer)
now5 = time.time()
print("Total time:", time.time()-now)
print("Editing time:", now5-now4) # Time to add features to the map
print("Interpolation:", sum(interpolation_times), "s.") # Time to do the interpolation
print("Feature manipulation:", sum(feature_times), "s.")
print("Number of features generated:", len(features_list))
```

