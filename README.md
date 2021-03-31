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

#### Experiment 1.1: On-the-fly with driver
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

dtrange = temporalController.dateTimeRangeForFrameNumber(currentFrameNumber)
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
Running this script for two different frames we obtain the following results  :
```
Total time: 0.07577347755432129 s.
Editing time: 0.023220062255859375 s.
Interpolation: 0.05182647705078125 s.
Feature manipulation: 0.00048804283142089844 s.
Number of features generated: 7
```
```
Total time: 0.10847806930541992 s.
Editing time: 0.04535698890686035 s.
Interpolation: 0.06148695945739746 s.
Feature manipulation: 0.0013802051544189453 s.
Number of features generated: 24
```
We can see that the interpolation time doesn't change much with the number of features generated. This is expected since interpolation is done on 100 features in any case, even if only a quarter (or tenth) actually yield a non-null result.
On the other hand, we can see the editing time (i.e. time to add features to the map) also logically increases with the number of features to be added to the layer.

By extrapolating these results, we can conclude that if this script was run at each frame (on-the-fly interpolation), the maximum framerate that could be achieved would be around 10 FPS.

#### Experiment 1.2: Buffering with driver
By modifying the last script slightly, we can try to generate features for the next FRAMES_NB frames and measure the performance.
```python
## Populate a layer stored in variable 'vlayer' with features using rows stored in variable 'rows'
## MAKE SURE to run import_rows_to_memory_using_driver.py and create_temporal_layer.py before
## running this script
import time
now = time.time()
FRAMES_NB = 50 # Number of frames to generate

canvas = iface.mapCanvas()
temporalController = canvas.temporalController()
currentFrameNumber = temporalController.currentFrameNumber()
features_list = []
interpolation_times = []
feature_times = []

# For every frame, use  mobility driver to retrieve valueAtTimestamp(frameTime) and create a corresponding feature
for i in range(FRAMES_NB):
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

print("Total time:", time.time()-now, "s.")
print("Editing time:", now5-now4, "s.") # Time to add features to the map
print("Interpolation:", sum(interpolation_times), "s.")
print("Feature manipulation:", sum(feature_times), "s.")
print("Number of features generated:", len(features_list))
```
Running this script with FRAMES_NB=50 at two different start frames we obtain the following results  :
```
Total time: 4.051093339920044 s.
Editing time: 1.458411693572998 s.
Interpolation: 2.5336971282958984 s.
Feature manipulation: 0.048734426498413086 s.
Number of features generated: 1151
```
```
Total time: 2.549457311630249 s.
Editing time: 0.48203563690185547 s.
Interpolation: 2.041699171066284 s.
Feature manipulation: 0.01581597328186035 s.
Number of features generated: 369
```
We can see that the interpolation time doesn't change much even though the number of features generated is very different. This is expected since the valueAtTimestamp() function from the driver is called 5000 times in both cases regardless of its return value. The editing time seems to be proportional to the number of features that are effectively added to the map. All in all, if we consider running this script takes between 3 and 4 seconds to generate 50 frames, the framerate's theoretical cap would be around 15 FPS, which isn't much better than on-the-fly interpolation.

#### Remarks
These experiments measure the performance of running the interpolation on the data and displaying features on the canvas. It is assumed that the trajectories for 100 rows have already been queried and stored in memory. Depending on how the query is performed (it could be advantageous to only store a small segment of the trajectory inside memory), this would also take time and be needed for an "in real time" animation. The theoritecal framerates obtained for both experiments are thus upper bounds on the final performance.

### Experiment 2
Let's now try to query the interpolation of the trajectory directly from the database (i.e. without using the mobilitydb python driver). We can do so using the postgisexecuteandloadsql algorithm, which allows us to obtain a layer with features directly.
```python
import processing
import time

FRAMES_NB = 1
temporalController = iface.mapCanvas().temporalController()
frame = temporalController.currentFrameNumber()
datetime=temporalController.dateTimeRangeForFrameNumber(frame).begin()
processing_times = []
add_features_times = []

# Processing algorithm parameters
parameters = { 'DATABASE' : "postgres", # Enter name of database to query
'SQL' : "",
'ID_FIELD' : 'id'
}

# Setup resulting vector layer
vlayer = QgsVectorLayer("Point", "points_4", "memory")
pr = vlayer.dataProvider()
pr.addAttributes([QgsField("id", QVariant.Int), QgsField("time", QVariant.DateTime)])
vlayer.updateFields()
tp = vlayer.temporalProperties()
tp.setIsActive(True)
tp.setMode(1)  # Single field with datetime
tp.setStartField("time")
vlayer.updateFields()
vlayer.startEditing()

# Populate vector layer with features at beginning time of every frame
now = time.time()
for i in range(FRAMES_NB):
    datetime=temporalController.dateTimeRangeForFrameNumber(frame+i).end()
    sql = "SELECT ROW_NUMBER() OVER() as id, '"+datetime.toString("yyyy-MM-dd HH:mm:ss")+"' as time, valueAtTimestamp(trip, '"+datetime.toString("yyyy-MM-dd HH:mm:ss")+"') as geom FROM trips"
    parameters['SQL'] = sql # Update algorithm parameters with sql query
    now = time.time()
    output = processing.run("qgis:postgisexecuteandloadsql", parameters) # Algorithm returns a layer containing the features, layer can be accessed by output['OUTPUT']
    now2 = time.time()
    processing_times.append(now2-now)
    vlayer.addFeatures(list(output['OUTPUT'].getFeatures())) # Add features from algorithm output layer to result layer
    add_features_times.append(time.time()-now2)
    
vlayer.commitChanges()
iface.vectorLayerTools().stopEditing(vlayer)

# Add result layer to project
QgsProject.instance().addMapLayer(vlayer)
print("Processing times : " + str(sum(processing_times)))
print("Add features times : " + str(sum(add_features_times)))
print("Total time : " + str(sum(processing_times)+sum(add_features_times)))
```
#### Experiment 2.1: On-the-fly interpolation
Running the previous script with FRAMES_NB=1 yields the following result:
```
Processing times : 0.07295393943786621
Add features times : 0.046048641204833984
Total time : 0.1190025806427002
```
Again we can see that we wouldn't be able to run the animation at more than 10 FPS.

#### Experiment 2.2: Buffering
Running the script with FRAMES_NB=50 and FRAMES_NB=200 gives the following:
```
Processing times : 2.367760419845581
Add features times : 0.9431586265563965
Total time : 3.3109190464019775
```
```
Processing times : 8.728699445724487
Add features times : 3.4965109825134277
Total time : 12.225210428237915
```
We can see performance here also seems to be capped at around 15 FPS.
#### Remarks
Due to an unknown bug, features that are generated using the algorithm don't actually show on the map unless the temporal controller is turned off, which makes it impossible to use unless the bug can be fixed.

### Experiment 3
Let's revisit experiment 1, but this time, instead of storing the whole tgeompoint column from the database into memory, let's only store the part needed to do the interpolation for the next 50 frames.
```python
## Import rows of mobilitydb table into a 'rows' variable
import psycopg2
import time
from mobilitydb.psycopg import register

canvas = iface.mapCanvas()
temporalController = canvas.temporalController()
currentFrameNumber = temporalController.currentFrameNumber()
FRAMES_NB = 1
connection = None
now = time.time()

try:
    # Set the connection parameters to PostgreSQL
    connection = psycopg2.connect(host='localhost', database='postgres', user='postgres', password='postgres')
    connection.autocommit = True

    # Register MobilityDB data types
    register(connection)

    # Open a cursor to perform database operations
    cursor = connection.cursor()

    # Query the database and obtain data as Python objects
    
    dt1 = temporalController.dateTimeRangeForFrameNumber(currentFrameNumber).begin().toString("yyyy-MM-dd HH:mm:ss")
    dt2 = temporalController.dateTimeRangeForFrameNumber(currentFrameNumber+FRAMES_NB-1).begin().toString("yyyy-MM-dd HH:mm:ss")
    select_query = "select atPeriod(trip, period('"+dt1+"', '"+dt2+"', true, true)) from trips"
    #select_query = "SELECT valueAtTimestamp(trip, '"+range.end().toString("yyyy-MM-dd HH:mm:ss-04")+"') FROM trips_test"
    
    cursor.execute(select_query)
    rows = cursor.fetchall()
    print("Query execution time:", time.time()-now)


except (Exception, psycopg2.Error) as error:
    print("Error while connecting to PostgreSQL", error)

finally:
    # Close the connection
    if connection:
        connection.close()
features_list = []
interpolation_times = []
feature_times = []

# For every frame, use  mobility driver to retrieve valueAtTimestamp(frameTime) and create a corresponding feature
for i in range(FRAMES_NB):
    dtrange = temporalController.dateTimeRangeForFrameNumber(currentFrameNumber+i)
    for row in rows:
        now2 = time.time()
        val = None
        if row[0]:
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

print("Total time:", time.time()-now, "s.")
print("Editing time:", now5-now4, "s.") # Time to add features to the map
print("Interpolation:", sum(interpolation_times), "s.") 
print("Feature manipulation:", sum(feature_times), "s.")
print("Number of features generated:", len(features_list))
```
Experiment 3.1: On-the-fly
Running this with NB_FRAMES=1 outputs the following:
```
Total time: 1.1713242530822754 s.
Query execution time: 1.0490577220916748
Total time without connection: 0.06578540802001953 s.
Editing time: 0.06384944915771484 s.
Interpolation: 0.0006940364837646484 s.
Feature manipulation: 0.0009610652923583984 s.
Number of features generated: 24
```
We can see that the interpolation time is very small. Outside of the time for the query to be executed and the connection to be established (which don't need to be done each frame), the performance is capped by the editing time. We can see that the total time without connection is ~0.065 seconds which would result in a framerate around 15 FPS.

####Experiment 3.2: Buffering
Let's now generate the features for all 50 frames of the period
```
Total time: 3.0664803981781006 s.
Query execution time: 1.0994305610656738
Total time without connection: 1.9227006435394287 s.
Editing time: 1.6872003078460693 s.
Interpolation: 0.16837859153747559 s.
Feature manipulation: 0.05574917793273926 s.
Number of features generated: 1204
```
We can see that the interpolation time is still very low. The main time consumption is due to the addition of the features to the layer and the time to run the query (which we now need to take into account). This brings us to a time of around 2.8 seconds to generate 50 frames, or ~18 FPS.

## Summary
Experiment|FPS cap|Remarks
----------|-------|-------
1 No buffer|10|The query result is assumed to be stored whole in memory
1 Buffer|15|
2 No buffer|10|Due to a bug, features don't actually show
2 Buffer|15|
3 No buffer|15|/
3 Buffer|18|
