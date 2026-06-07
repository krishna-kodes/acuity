from pydantic import BaseModel


class ModuleOut(BaseModel):
    id: str
    title: str
    label: str
    description: str = ""


class ModulesResponse(BaseModel):
    modules: list[ModuleOut]


class ModulePatchRequest(BaseModel):
    modules: list[ModuleOut]
