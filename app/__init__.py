from flask_restx import Api

from app.main.exceptions import DefaultException, ValidationException
from app.main.util import ActivationDTO, DefaultResponsesDTO, TableDTO

from .main.controller import (
    agent_ns,
    anonymization_ns,
    anonymization_record_ns,
    anonymization_type_ns,
    auth_ns,
    database_ns,
    encryption_ns,
    password_ns,
    sql_log_ns,
    user_ns,
    valid_database_ns,
)

authorizations = {"apikey": {"type": "apiKey", "in": "header", "name": "Authorization"}}

api = Api(
    authorizations=authorizations,
    title="SysPAD API",
    version="1.2.0",
    description="Data protection system based on encryption and anonymization",
    security="apikey",
)

api.add_namespace(user_ns, path="/user")
api.add_namespace(auth_ns, path="/login")
api.add_namespace(password_ns, path="/password")
api.add_namespace(valid_database_ns, path="/valid_database")
api.add_namespace(database_ns, path="/database")
api.add_namespace(anonymization_type_ns, path="/anonymization_type")
api.add_namespace(anonymization_record_ns, path="/anonymization_record")
api.add_namespace(encryption_ns, path="/encryption")
api.add_namespace(anonymization_ns, path="/anonymization")
api.add_namespace(sql_log_ns, path="/sql_log")
api.add_namespace(agent_ns, path="/agent")

api.add_namespace(DefaultResponsesDTO.api)
api.add_namespace(TableDTO.api)
api.add_namespace(ActivationDTO.api)

# Exception Handler
api.errorhandler(DefaultException)


@api.errorhandler(ValidationException)
def handle_validation_exception(error):
    """Return a list of errors and a message"""
    return {"errors": error.errors, "message": error.message}, error.code
