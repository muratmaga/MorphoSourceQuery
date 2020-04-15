import SimpleITK as sitk
import sitkUtils
import os
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging
import numpy as np
import string
import requests
import math
import warnings
from requests.packages.urllib3.exceptions import InsecureRequestWarning
import zipfile
import io

#
# MorphoSourceImport
#
#define global variable for default login
base_url = "https://www.morphosource.org/api/v1/find/"
end_url = "&sort=specimen.element,taxonomy_names.ht_order"
warnings.simplefilter('ignore',InsecureRequestWarning)
slicer.userNameDefault = "SlicerMorph@gmail.com"
slicer.passwordDefault = ""

# check for required python packages
try:
  import pandas
except:
  slicer.util.pip_install('pandas')
  import pandas 


class MorphoSourceImport(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "MorphoSourceImport" # TODO make this more human readable by adding spaces
    self.parent.categories = ["SlicerMorph.SlicerMorph Labs"]
    self.parent.dependencies = []
    self.parent.contributors = ["Murat Maga (UW), Sara Rolfe (UW), Arthur Porto(SCRI)"] # replace with "Firstname Lastname (Organization)"
    self.parent.helpText = """
This module provides a keyword search to query and load 3D models from the MorphoSource database into the 3D Slicer scene.
"""
    self.parent.acknowledgementText = """
This module was developed by Sara Rolfe and  Murat Maga, for the NSF HDR  grant, "Biology Guided Neural Networks" (Award Number: 1939505).
https://www.nsf.gov/awardsearch/showAward?AWD_ID=1939505&HistoricalAwards=false
"""


#
# MorphoSourceImportWidget
#

class MorphoSourceImportWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)
    # Instantiate and connect widgets ...
    #
    # Input/Export Area
    #
    IOCollapsibleButton = ctk.ctkCollapsibleButton()
    IOCollapsibleButton.text = "Input and Export"
    self.layout.addWidget(IOCollapsibleButton)

    # Layout within the dummy collapsible button
    #IOFormLayout = qt.QFormLayout(IOCollapsibleButton)
    IOFormLayout= qt.QFormLayout(IOCollapsibleButton)

    #
    # Username input
    #
    self.userNameInput = qt.QLineEdit()
    self.userNameInput.setText(slicer.userNameDefault)
    self.userNameInput.setToolTip( "Input MorphoSource account username" )
    IOFormLayout.addRow("MorphSource Username: ", self.userNameInput)

    #
    # Password input
    #

    self.passwordInput = qt.QLineEdit()
    self.passwordInput.setText(slicer.passwordDefault)
    self.passwordInput.setToolTip( "Input MorphoSource account password" )
    IOFormLayout.addRow("MorphSource Password: ", self.passwordInput)

    #
    # Login button
    #
    self.loginButton = qt.QPushButton("Log in")
    self.loginButton.toolTip = "Log into the Morphosource database"
    self.loginButton.enabled = False
    IOFormLayout.addRow(self.loginButton)

    #
    # Query parameter area
    #
    parametersCollapsibleButton = ctk.ctkCollapsibleButton()
    parametersCollapsibleButton.text = "Query parameters"
    self.layout.addWidget(parametersCollapsibleButton)

    # Layout within the dummy collapsible button
    parametersFormLayout = qt.QFormLayout(parametersCollapsibleButton)

    #
    # Username input
    #
    self.orderInput = qt.QLineEdit()
    self.orderInput.setToolTip( "Input the the specimen order, eg: 'Euprimates' " )
    parametersFormLayout.addRow("Query order: ", self.orderInput)

    #
    # Username input
    #
    self.elementInput = qt.QLineEdit()
    self.elementInput.setToolTip( "Input the speciment element, eg: 'Cranuim' " )
    parametersFormLayout.addRow("Query element: ", self.elementInput)

    #

    # Submit query Button
    #
    self.submitQueryButton = qt.QPushButton("Submit query")
    self.submitQueryButton.toolTip = "Query the MorphoSource database for 3D models. This may take a few minutes."
    self.submitQueryButton.enabled = False
    parametersFormLayout.addRow(self.submitQueryButton)
    
    #
    # Query results area
    #
    resultsCollapsibleButton = ctk.ctkCollapsibleButton()
    resultsCollapsibleButton.text = "Query results:"
    resultsCollapsibleButton.collapsed = False
    self.layout.addWidget(resultsCollapsibleButton)
    resultsFormLayout = qt.QFormLayout(resultsCollapsibleButton)

    self.resultsModel = qt.QStandardItemModel()
    self.resultsTable = qt.QTableView()
    self.resultsTable.horizontalHeader().stretchLastSection = True
    self.resultsTable.horizontalHeader().visible = False
    self.resultsTable.verticalHeader().visible = False
    self.resultsTable.setSelectionBehavior(qt.QAbstractItemView().SelectRows)
    self.resultsTable.setModel(self.resultsModel)
    resultsFormLayout.addRow(self.resultsTable)

    self.loadResultsButton = qt.QPushButton("Load selected models")
    self.loadResultsButton.toolTip = "Load the selected models into the scene."
    self.loadResultsButton.enabled = False
    resultsFormLayout.addRow(self.loadResultsButton)


    # connections
    self.loginButton.connect('clicked(bool)', self.onLogin)
    self.userNameInput.connect('textChanged(const QString &)', self.onLoginStringChanged)
    self.passwordInput.connect('textChanged(const QString &)', self.onLoginStringChanged)
    self.orderInput.connect('textChanged(const QString &)', self.onQueryStringChanged)
    self.elementInput.connect('textChanged(const QString &)', self.onQueryStringChanged)
    self.submitQueryButton.connect('clicked(bool)', self.onSubmitQuery)
    self.loadResultsButton.connect('clicked(bool)', self.onLoadResults)

    # Add vertical spacer
    self.layout.addStretch(1)

    # Refresh Apply button state
    self.onLoginStringChanged()
    self.onQueryStringChanged()

  def cleanup(self):
    pass

  def onLoginStringChanged(self):
    self.loginButton.enabled = bool(self.userNameInput.text is not "") and bool(self.passwordInput.text is not "")

  def onQueryStringChanged(self):
    self.submitQueryButton.enabled = bool(self.orderInput.text is not "") and bool(self.elementInput.text is not "")

  def onLogin(self):
    logic = MorphoSourceImportLogic()
    self.session = logic.runLogin(self.userNameInput.text, self.passwordInput.text)

  def onSubmitQuery(self):
      self.resultsTable.model().clear() # clear result from any previous run
      queryDictionary =  {
        "order": self.orderInput.text,
        "element": self.elementInput.text
      }
      logic = MorphoSourceImportLogic()
      self.result_dataframe = logic.runQuery(queryDictionary, self.session)
      if not self.result_dataframe.empty:
        self.populateTable()
        self.loadResultsButton.enabled = True

  def populateTable(self):
    self.resultsTable.horizontalHeader().visible = True
    self.resultsModel.setHorizontalHeaderLabels(self.result_dataframe.columns)
    [rowCount,columnCount]=self.result_dataframe.shape
    for i in range(rowCount):
      for j in range(columnCount):
        item = qt.QStandardItem()
        item.setText(self.result_dataframe.iloc[i,j])
        self.resultsModel.setItem(i, j, item)
  
  def onLoadResults(self):
    selection = self.resultsTable.selectionModel().selectedRows()
    selectionList = []
    for i in range(len(selection)):
      selectionList.append(selection[i].row())
    selectedResults = self.result_dataframe.iloc[selectionList]
    logic = MorphoSourceImportLogic()
    logic.runImport(selectedResults, self.session)
    
class LogDataObject:
  """This class i
     """
  def __init__(self):
    self.FileType = "NULL"
    self.X  = "NULL"
    self.Y = "NULL"
    self.Z = "NULL"
    self.Resolution = "NULL"
    self.Prefix = "NULL"
    self.SequenceStart = "NULL"
    self.SeqenceEnd = "NULL"

#
# MorphoSourceImportLogic
#
class MorphoSourceImportLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget.
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """
  
  def runImport(self, dataFrame, session):
    for index in dataFrame.index:
      print('Downloading file for specimen ID ' + dataFrame['specimen_id'][index])
      response = session.get(dataFrame['download_link'][index])
      zip_file = zipfile.ZipFile(io.BytesIO(response.content))
      extensions = ('.stl','.ply', '.obj')
      model=[zip_file.extract(file,slicer.app.defaultScenePath) for file in zip_file.namelist() if file.endswith(extensions)]
      slicer.util.loadModel(model[0])
     
  def process_json(self,response_json, session):
    #Initializing the database
    database=[]
    #Finding the surface files and querying for the corresponding specimen information
    for result in response_json['results']:
      for media in result['medium.media']:
        if media['mimetype'] in ['application/ply','application/obj','application/stl']:
          #Querying for specimen information (accessed through a separate query)
          file_id=result['specimen.specimen_id']
          query_id = f"{base_url}specimens?q=specimen.specimen_id:{file_id}{end_url}"
          response = session.get(query_id).json()
          taxa = response['results'][0]['taxonomy_name'][0]['names'][0]

          #Generating the database
          database.append({'order': taxa['ht_order'], 'genus': taxa['genus'], 'species': taxa['species'],
            'filetype': media['mimetype'][-3:], 'filesize': media['filesize'],
            'element': media['element'], 'download_link': media['download'],
            'media_file_id': media['media_file_id'], 'specimen_id': result['specimen.specimen_id'], 'project_id': result['project.project_id']})
    return database

  def findDownload(self, query, session):

    #Initial query in which we get the total number of items in the database
    query_string=f"{base_url}media?q=taxonomy_names.ht_order:{query['order']} AND specimen.element:{query['element']}{end_url}&limit=1"
    response = session.get(query_string)
    totalResults = response.json()['totalResults']
    page_number = math.ceil(totalResults/25) #current page limit is 25

    #Initializing database as a list
    database=[]
    error_count=0

    #Iterating through resulting pages
    for page in range(page_number):
      sub_query = session.get(f"{query_string[:-1]}{str(page)}")
      try:
        decoded_json = sub_query.json()
        database = database + self.process_json(decoded_json,session)
      except:
        error_count += 1
        print(f'A total of {error_count} pages could not be decoded')
    return database

  def runQuery(self, dictionary, session):
    """
    Run the query using the data dictionary
    """
    print('Beginning scraping for download links')
    download_list = self.findDownload(dictionary, session)
    if download_list == None:
      print(f"No links found for query {str(id)}")
      return pandas.DataFrame()
    else:
      validResults = self.checkValidResults(pandas.DataFrame(download_list))
      return validResults
  
        
  def checkValidResults(self, dataFrame):
    # only return meshes with a download link
    downloadInfo=dataFrame.download_link
    validFileIndexes=[]
    for i in range(downloadInfo.size):
      if 'http' in downloadInfo[i]:
        validFileIndexes.append(i)
    return dataFrame.iloc[validFileIndexes].reset_index(drop=True)
      
    
  def runLogin(self, username, password):
    session_requests = requests.session()
    login_url = 'http://www.morphosource.org/LoginReg/login'
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    data = 'username=' + username +'&password=' + password
    login_result = session_requests.post(login_url, params= data, verify= False)
    print("Attempting log in: ", login_result.ok)
    return session_requests

  def takeScreenshot(self,name,description,type=-1):
    # show the message even if not taking a screen shot
    slicer.util.delayDisplay('Take screenshot: '+description+'.\nResult is available in the Annotations module.', 3000)

    lm = slicer.app.layoutManager()
    # switch on the type to get the requested window
    widget = 0
    if type == slicer.qMRMLScreenShotDialog.FullLayout:
      # full layout
      widget = lm.viewport()
    elif type == slicer.qMRMLScreenShotDialog.ThreeD:
      # just the 3D window
      widget = lm.threeDWidget(0).threeDView()
    elif type == slicer.qMRMLScreenShotDialog.Red:
      # red slice window
      widget = lm.sliceWidget("Red")
    elif type == slicer.qMRMLScreenShotDialog.Yellow:
      # yellow slice window
      widget = lm.sliceWidget("Yellow")
    elif type == slicer.qMRMLScreenShotDialog.Green:
      # green slice window
      widget = lm.sliceWidget("Green")
    else:
      # default to using the full window
      widget = slicer.util.mainWindow()
      # reset the type so that the node is set correctly
      type = slicer.qMRMLScreenShotDialog.FullLayout

    # grab and convert to vtk image data
    qimage = ctk.ctkWidgetsUtils.grabWidget(widget)
    imageData = vtk.vtkImageData()
    slicer.qMRMLUtils().qImageToVtkImageData(qimage,imageData)

    annotationLogic = slicer.modules.annotations.logic()
    annotationLogic.CreateSnapShot(name, description, type, 1, imageData)


class MorphoSourceImportTest(ScriptedLoadableModuleTest):
  """
  This is the test case for your scripted module.
  Uses ScriptedLoadableModuleTest base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setUp(self):
    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    slicer.mrmlScene.Clear(0)

  def runTest(self):
    """Run as few or as many tests as needed here.
    """
    self.setUp()
    self.test_MorphoSourceImport1()

  def test_MorphoSourceImport1(self):
    """ Ideally you should have several levels of tests.  At the lowest level
    tests should exercise the functionality of the logic with different inputs
    (both valid and invalid).  At higher levels your tests should emulate the
    way the user would interact with your code and confirm that it still works
    the way you intended.
    One of the most important features of the tests is that it should alert other
    developers when their changes will have an impact on the behavior of your
    module.  For example, if a developer removes a feature that you depend on,
    your test should break so they know that the feature is needed.
    """

    self.delayDisplay("Starting the test")
    #
    # first, get some data
    #
    import urllib
    downloads = (
        ('http://slicer.kitware.com/midas3/download?items=5767', 'FA.nrrd', slicer.util.loadVolume),
        )

    for url,name,loader in downloads:
      filePath = slicer.app.temporaryPath + '/' + name
      if not os.path.exists(filePath) or os.stat(filePath).st_size == 0:
        logging.info('Requesting download %s from %s...\n' % (name, url))
        urllib.urlretrieve(url, filePath)
      if loader:
        logging.info('Loading %s...' % (name,))
        loader(filePath)
    self.delayDisplay('Finished with download and loading')

    volumeNode = slicer.util.getNode(pattern="FA")
    logic = MorphoSourceImportLogic()
    self.assertIsNotNone( logic.hasImageData(volumeNode) )
    self.delayDisplay('Test passed!')
