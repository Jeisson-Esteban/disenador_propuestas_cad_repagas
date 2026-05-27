"""
Pydantic models del formulario y la propuesta de equipos.

Estos schemas describen la forma del JSON que envia el frontend (FormularioCliente)
y la estructura que devuelve el LLM (PropuestaEquipos), mas el resultado tras
resolver contra el catalogo (EquipoResuelto).
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class EquipoSeleccionado(BaseModel):
    """Un equipo que el LLM ha decidido incluir en el diseño."""
    tipo: str = Field(description="Tipo de equipo: cocina_gas, freidora_gas, fry_top_gas, plancha, neutro, horno_combinado, lavavajillas, mesa_refrig_conservacion, etc.")
    cantidad: int = Field(default=1, description="Número de unidades necesarias")
    alimentacion: str = Field(default="gas", description="gas o electrico")
    ancho_mm_preferido: Optional[int] = Field(default=None, description="Ancho preferido en mm (400, 800, 1200). Null = el LLM no tiene preferencia")
    razon: str = Field(description="Justificación breve de por qué se incluye este equipo")


class PropuestaEquipos(BaseModel):
    """Salida estructurada del LLM: lista completa de equipos para el proyecto."""
    nombre_proyecto: str = Field(description="Nombre descriptivo del proyecto")
    layout: str = Field(default="L", description="Tipo de distribución: lineal, L, U, paralelo")
    zona_coccion: list[EquipoSeleccionado] = Field(description="Equipos para la línea de cocción mural")
    zona_frio: list[EquipoSeleccionado] = Field(default_factory=list, description="Equipos de refrigeración")
    zona_lavado: list[EquipoSeleccionado] = Field(default_factory=list, description="Equipos de lavado")
    zona_horno: list[EquipoSeleccionado] = Field(default_factory=list, description="Hornos combinados")
    notas: str = Field(default="", description="Notas adicionales sobre el diseño")


class InfoProyecto(BaseModel):
    """Datos generales del proyecto."""
    nombre: Optional[str] = None
    tipo_negocio: str = Field(description="restaurante, taperia, fast_food, pizzeria, hotel, hospital, catering")
    concepto: Optional[str] = None               # "parrilla argentina", "cocina mediterránea"
    comensales: int = Field(description="Número de comensales por servicio")
    superficie_m2: Optional[float] = None
    presupuesto_max: Optional[float] = None

class DesnivelesSuelo(BaseModel):
    """Información sobre desniveles en el suelo."""
    existe: bool = False
    detalle: Optional[str] = None                # "pendiente 3.95%"

class InfoTecnica(BaseModel):
    """Datos técnicos de la cocina / local."""
    tipo_proyecto: str = "nuevo"                  # "nuevo" | "renovacion"
    retirar_cocina_antigua: bool = False
    existe_plano_tecnico: bool = False
    altura_suelo_techo_m: Optional[float] = None
    material_paredes: list[str] = Field(default_factory=list)
    material_suelo: Optional[str] = None
    desniveles_suelo: DesnivelesSuelo = Field(default_factory=DesnivelesSuelo)
    dimensiones_accesos: Optional[dict[str, float]] = None  # {"puerta_principal_m": 1.4, ...}

class InfoEnergia(BaseModel):
    """Energía e instalaciones disponibles."""
    tipo_energia: str = "gas"                     # "gas" | "electrico" | "mixto"
    tipo_gas: Optional[str] = None                # "gas_natural" | "propano"
    caudal_gas_disponible: Optional[str] = None
    tipo_electrico: Optional[str] = None          # "trifasico" | "monofasico"
    potencia_contratada_kw: Optional[float] = None

class InfoEquipamiento(BaseModel):
    """Necesidades de equipamiento por zona."""
    coccion: list[str] = Field(default_factory=list)
    refrigeracion: list[str] = Field(default_factory=list)
    lavado: list[str] = Field(default_factory=list)
    otros: list[str] = Field(default_factory=list)
    preferencias_colocacion: Optional[str] = None
    marcas_preferidas: list[str] = Field(default_factory=list)

class InfoGastronomica(BaseModel):
    """Identidad gastronómica del negocio."""
    identidad: Optional[str] = None               # "tradicional", "creativa", "alta_cocina", "fusion"
    tipo_cocina: Optional[str] = None             # "parrilla", "japonesa", etc.
    estructura_menu: list[str] = Field(default_factory=list)  # ["carta", "menu_mediodia"]
    cantidad_platos: Optional[int] = None
    ingredientes_frescos: list[str] = Field(default_factory=list)
    ingredientes_congelados: list[str] = Field(default_factory=list)
    cuarta_gama: list[str] = Field(default_factory=list)
    quinta_gama: list[str] = Field(default_factory=list)

class InfoLavado(BaseModel):
    """Vajilla y utensilios a lavar."""
    platos: Optional[int] = None
    vasos: Optional[int] = None
    copas: Optional[int] = None
    cubiertos: Optional[int] = None
    tazas: Optional[int] = None
    otros_utensilios: list[str] = Field(default_factory=list)
    consideraciones: list[str] = Field(default_factory=list)  # ["desagues", "trampas_grasas"]

class GamaProducto(BaseModel):
    """Productos de una gama con kg aproximados."""
    productos: list[str] = Field(default_factory=list)
    kg_aproximados: Optional[float] = None

class SegundaGama(BaseModel):
    """Segunda gama (conservas) con estanterías."""
    productos: list[str] = Field(default_factory=list)
    necesita_estanterias: bool = False

class InfoRefrigeracion(BaseModel):
    """Producto que almacena, organizado por gamas."""
    primera_gama: GamaProducto = Field(default_factory=GamaProducto)
    segunda_gama: SegundaGama = Field(default_factory=SegundaGama)
    tercera_gama: GamaProducto = Field(default_factory=GamaProducto)
    cuarta_gama: GamaProducto = Field(default_factory=GamaProducto)
    quinta_gama: GamaProducto = Field(default_factory=GamaProducto)

class InfoPersonal(BaseModel):
    """Personal de cocina."""
    personas_en_cocina: Optional[int] = None
    roles: list[str] = Field(default_factory=list)

class InfoEscalabilidad(BaseModel):
    """Escalabilidad y futuro."""
    puede_ampliar_carta: Optional[bool] = None
    espacio_mas_equipamiento: Optional[bool] = None
    instalacion_permite_mas_potencia: Optional[bool] = None

class InfoFormacion(BaseModel):
    """Formación sobre equipamiento."""
    requiere_formacion: bool = False
    equipos_formacion: list[str] = Field(default_factory=list)

class FormularioCliente(BaseModel):
    """Datos completos del cliente — cuestionario real Repagas."""
    proyecto: InfoProyecto
    parte_tecnica: InfoTecnica = Field(default_factory=InfoTecnica)
    energia: InfoEnergia = Field(default_factory=InfoEnergia)
    necesidades_equipamiento: InfoEquipamiento = Field(default_factory=InfoEquipamiento)
    identidad_gastronomica: InfoGastronomica = Field(default_factory=InfoGastronomica)
    lavado: InfoLavado = Field(default_factory=InfoLavado)
    refrigeracion: InfoRefrigeracion = Field(default_factory=InfoRefrigeracion)
    personal: InfoPersonal = Field(default_factory=InfoPersonal)
    escalabilidad: InfoEscalabilidad = Field(default_factory=InfoEscalabilidad)
    formacion: InfoFormacion = Field(default_factory=InfoFormacion)
    visita_fabrica: bool = False

    @property
    def comensales(self) -> int:
        return self.proyecto.comensales

    @property
    def tipo_negocio(self) -> str:
        return self.proyecto.tipo_negocio

    @property
    def energia_principal(self) -> str:
        return self.energia.tipo_energia


class EquipoResuelto(BaseModel):
    """Un equipo ya resuelto contra la base de datos con medidas reales."""
    modelo: str
    tipo: str
    ancho_mm: int
    fondo_mm: int
    alto_mm: int
    pvp_eur: Optional[float] = None
    serie: str = ""
    cantidad: int = 1
    zona: str = ""  # coccion, frio, lavado, horno


