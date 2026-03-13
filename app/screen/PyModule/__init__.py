# PyModule/__init__.py

#Welcome Screen
from .WelcomeScreen import WelcomeScreen

#Screen A
from .A_SensorSettingsScreen import SensorSettingsScreen

#Screen B
from .B_WorkConfigScreen import WorkConfigScreen
from .B_DataGenerationScreen import DataGenerationScreen

#Screen C
from .C_DataSelectionScreen import DataSelectionScreen
from .C_ModelTrainingScreen import ModelTrainingScreen
from .C_TrainingResultsScreen import TrainingResultsScreen

#Screen D
from .D_AIDetectionExecutionScreen import AIDetectionExecutionScreen
from .D_DetectionResultsScreen import DetectionResultsScreen

#Screen E
from .E_SystemSettingsScreen import SystemSettingsScreen
from .E_IniSettingsScreen import IniSettingsScreen

#Utils
from .utils.lang_manager import LangManager
from .utils.datatable_manager import DataTableManager
