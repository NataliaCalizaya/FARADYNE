class FaradyneException(Exception):
    pass

class ProjectNotFoundException(FaradyneException):
    pass

class Model2DNotFoundException(FaradyneException):
    pass

class InvalidFileFormatException(FaradyneException):
    pass

class ParseException(FaradyneException):
    pass

class GeometryException(FaradyneException):
    pass
