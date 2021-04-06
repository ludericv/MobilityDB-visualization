## Create a temporal layer (variable 'vlayer') with single field for datetime
## Do not forget to manually change this layer's CRS in Properties > Source
vlayer = QgsVectorLayer("Point", "points_3", "memory")
pr = vlayer.dataProvider()
pr.addAttributes([QgsField("time", QVariant.DateTime)])
vlayer.updateFields()
tp = vlayer.temporalProperties()
tp.setIsActive(True)
tp.setMode(1) #single field with datetime
tp.setStartField("time")
vlayer.updateFields()
QgsProject.instance().addMapLayer(vlayer)
