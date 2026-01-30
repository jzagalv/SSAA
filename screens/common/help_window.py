from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QPushButton
from PyQt5.QtCore import Qt


class HelpWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Manual de Ayuda – Calculadora de Bancos de Baterías")
        self.resize(900, 700)

        layout = QVBoxLayout(self)

        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        layout.addWidget(self.browser)

        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)
        btn_close.setDefault(True)
        layout.addWidget(btn_close, alignment=Qt.AlignRight)

        self.browser.setHtml(self._build_html())

    # ------------------------------------------------------------------
    # Contenido HTML del manual
    # ------------------------------------------------------------------
    def _build_html(self) -> str:
        return """
        <html>
        <head>
            <style>
                body {
                    font-family: Segoe UI, Arial, sans-serif;
                    font-size: 10pt;
                }
                h1 {
                    color: #2c3e50;
                    border-bottom: 1px solid #bdc3c7;
                    padding-bottom: 4px;
                }
                h2 {
                    color: #2c3e50;
                    margin-top: 18px;
                }
                h3 {
                    color: #34495e;
                    margin-top: 12px;
                }
                ul, ol {
                    margin-top: 4px;
                    margin-bottom: 4px;
                }
                .panel {
                    background-color: #f4f6f7;
                    border: 1px solid #d5d8dc;
                    padding: 6px 8px;
                    margin: 8px 0;
                }
                code {
                    font-family: Consolas, monospace;
                    background-color: #f4f4f4;
                    padding: 1px 3px;
                }
            </style>
        </head>
        <body>

        <h1>Calculadora de Bancos de Baterías – Manual de uso</h1>

        <p>
        Esta aplicación permite modelar los servicios auxiliares de una subestación
        eléctrica, registrar sus gabinetes, componentes y consumos, y calcular
        la demanda que deberá alimentar el banco de baterías C.C. y las barras C.A.
        </p>

        <div class="panel">
            <b>Flujo de trabajo recomendado</b>
            <ol>
                <li><b>Archivo:</b> crear un nuevo proyecto o abrir uno existente.</li>
                <li><b>Proyecto:</b> completar datos generales de la S/E.</li>
                <li><b>Instalaciones:</b> definir salas y gabinetes.</li>
                <li><b>Componentes:</b> asignar equipos y consumos a cada gabinete,
                    incluyendo el tipo de alimentador.</li>
                <li><b>Alimentación tableros:</b> definir desde qué barras se alimenta
                    cada tablero y sus tableros padres.</li>
                <li><b>Validar:</b> revisar inconsistencias y, si es necesario, analizar
                    el grafo de dependencias.</li>
                <li><b>Guardar proyecto</b> desde la pestaña Archivo o desde el menú superior.</li>
            </ol>
        </div>

        <h2>1. Barra de menús</h2>

        <h3>1.1 Menú Archivo</h3>
        <ul>
            <li><b>Guardar proyecto</b>: guarda toda la información del proyecto en el archivo
                seleccionado en la pestaña <b>Archivo</b>. Si no se ha definido ruta, el programa
                avisará que primero debes indicar una carpeta y nombre de archivo.</li>
        </ul>

        <h3>1.2 Menú Herramientas</h3>
        <ul>
            <li><b>Base de datos de componentes…</b> abre la ventana donde se administra
                la base de datos de equipos (modelos estándar, potencias, tipo de consumo, etc.).
                Cualquier cambio se verá reflejado luego en la pestaña <b>Componentes</b>.</li>
        </ul>

        <h3>1.3 Menú Ayuda</h3>
        <ul>
            <li><b>Manual de usuario</b>: abre esta ventana.</li>
        </ul>

        <p>
        Además, al cerrar la aplicación el sistema detecta si hay cambios pendientes y
        pregunta si deseas guardar el proyecto antes de salir.
        </p>

        <h2>2. Pestaña Archivo</h2>

        <p>
        En esta pestaña defines la ubicación del archivo de proyecto (formato JSON) y
        realizas las operaciones básicas:
        </p>
        <ul>
            <li><b>Nuevo proyecto</b>: inicializa la información en blanco.</li>
            <li><b>Abrir proyecto</b>: carga un archivo existente, incluyendo salas,
                gabinetes, componentes y configuración de alimentación.</li>
            <li><b>Guardar</b>: escribe el estado actual del modelo en el archivo seleccionado.</li>
        </ul>

        <div class="panel">
            <b>Consejo:</b> utiliza siempre la misma carpeta para los archivos de proyecto.
            Así será más fácil mantener versiones y respaldos.
        </div>

        <h2>3. Pestaña Proyecto</h2>

        <p>
        Permite ingresar los datos generales del proyecto: identificación de la
        subestación, tensiones, niveles de corriente, criterios de diseño, etc.
        Estos datos no afectan directamente los cálculos de alimentación, pero forman
        parte de la documentación del proyecto y aparecen en los reportes futuros.
        </p>

        <h2>4. Pestaña Instalaciones</h2>

        <p>
        Aquí se modela la estructura física básica:
        </p>
        <ul>
            <li><b>Salas</b>: por ejemplo “Sala de control”, “Sala GIS 110 kV”, etc.</li>
            <li><b>Gabinetes</b>: cada tablero o gabinete se asocia a una sala y se identifica
                por un <b>TAG</b> y una descripción.</li>
        </ul>

        <p>
        Los gabinetes definidos aquí son los que luego se mostrarán en la pestaña
        <b>Componentes</b> (lista de la izquierda) y en <b>Alimentación tableros</b>.
        Cuando se modifican las salas o gabinetes, las otras pestañas se actualizan
        automáticamente.
        </p>

        <h2>5. Pestaña Componentes</h2>

        <p>
        Esta pestaña es el corazón del modelado de consumos por gabinete. Está dividida en:
        </p>
        <ul>
            <li>Lista de <b>Gabinetes</b> (lado izquierdo).</li>
            <li><b>Diseño del gabinete</b> en el centro, con tarjetas que representan
                los componentes instalados.</li>
            <li>Lista de <b>Componentes disponibles</b> (lado derecho) tomada de la
                base de datos de componentes.</li>
            <li>Tabla <b>Componentes del gabinete</b> en la parte inferior.</li>
        </ul>

        <h3>5.1 Tabla de componentes del gabinete</h3>

        <p>
        Cada fila de la tabla representa un componente asociado al gabinete seleccionado.
        Las columnas típicas son:
        </p>
        <ul>
            <li><b>Modelo / TAG / Marca / Modelo</b>: identificación del equipo.</li>
            <li><b>P [W]</b> y <b>P [VA]</b>: potencia en W o VA. Puedes indicar ambas pero,
                si activas <b>Usar VA</b>, el cálculo utilizará el valor en VA.</li>
            <li><b>Usar VA</b>: casilla que indica qué potencia usar en el cálculo.</li>
            <li><b>Alimentador</b>:
                <ul>
                    <li><b>General</b>: el consumo se considera dentro de la alimentación
                        general del tablero.</li>
                    <li><b>Individual</b>: el componente se alimenta por un alimentador
                        independiente. En la pestaña <b>Alimentación tableros</b> aparecerá
                        una fila propia para este componente.</li>
                    <li><b>Indirecta</b>: permite representar consumos que dependen de
                        otro alimentador (por ejemplo motores comandados desde otro tablero).
                        Se usa junto con la pestaña de alimentación de tableros.</li>
                </ul>
            </li>
            <li><b>Tipo Consumo</b>: C.C. permanente, C.C. momentáneo, C.A. esencial, etc.</li>
            <li><b>Fase</b>: 1F / 3F (aplicable a consumos en C.A.).</li>
            <li><b>Origen</b>: indica si los datos provienen de la base de datos o han sido
                definidos por el usuario. Cuando el origen es “Por Usuario”, el campo
                <b>Alimentador</b> puede ajustarse directamente.</li>
        </ul>

        <div class="panel">
            <b>Nota sobre la rueda del mouse:</b> los desplegables (combobox) han sido
            configurados para no cambiar su valor al girar la rueda del mouse o usar
            el gesto de scroll del trackpad por accidente. Para modificar un valor es
            necesario hacer clic y seleccionar explícitamente la opción.
        </div>

        <h2>6. Pestaña Alimentación tableros</h2>

        <p>
        En esta pestaña se define desde qué barras se alimenta cada tablero y sus
        componentes con alimentador individual. La tabla muestra:
        </p>
        <ul>
            <li><b>Tag / Descripción</b>: gabinete o componente.</li>
            <li><b>C.C. B1 / C.C. B2</b>: casillas para indicar desde qué barra de C.C.
                se alimenta.</li>
            <li><b>C.A. Esencial / C.A. No esencial</b>: indicación de alimentación en C.A.</li>
            <li><b>Tablero Padre C.C. B1</b> y <b>Tablero Padre C.C. B2</b>:
                tablero desde el que se alimenta cada barra de C.C.</li>
            <li><b>Tablero Padre C.A. Esencial</b> y <b>Tablero Padre C.A. No esencial</b>:
                tableros padres para las barras de C.A.</li>
        </ul>

        <p>
        Las celdas de “Tablero Padre” se habilitan sólo cuando la casilla correspondiente
        a la barra está marcada. Esto evita definir tableros padres incoherentes.
        </p>

        <h3>6.1 Reglas para General e Individual</h3>

        <ul>
            <li>Si un gabinete tiene únicamente <b>alimentación General</b>, la tabla
                muestra una sola fila para el tablero (la potencia total se considera en
                ese alimentador general).</li>
            <li>Si existen componentes con <b>alimentación Individual</b>, para cada uno
                se crea una fila adicional en la tabla de Alimentación tableros, con su
                propia configuración de barras y tablero padre.</li>
            <li>De esta forma puedes distinguir qué parte de la carga cuelga del
                alimentador general del tablero y qué parte lo hace desde alimentadores
                independientes.</li>
        </ul>

        <h3>6.2 Validación de inconsistencias</h3>

        <p>
        El botón <b>Validar inconsistencias</b> recorre todos los gabinetes y componentes
        en busca de problemas frecuentes, por ejemplo:
        </p>
        <ul>
            <li>Se marcó una barra (C.C. B1, C.A. Esencial, etc.) pero no se definió
                un tablero padre.</li>
            <li>Se indicó un tablero padre cuyo TAG no existe en la lista de gabinetes.</li>
        </ul>
        <p>
        Los resultados se muestran en una lista donde puedes ir revisando y corrigiendo
        cada situación.
        </p>

        <h3>6.3 Grafo de dependencias</h3>

        <p>
        El botón <b>Ver grafo de dependencias…</b> abre una ventana flotante con:
        </p>
        <ul>
            <li>Una lista de gabinetes a la izquierda.</li>
            <li>Un diagrama a la derecha con las cadenas de alimentación para:
                <b>C.C. B1</b>, <b>C.C. B2</b>, <b>C.A. Esencial</b> y
                <b>C.A. No esencial</b>.</li>
        </ul>

        <p>
        Al seleccionar un gabinete, se dibuja la cadena de tableros desde el tablero
        “raíz” hasta el gabinete elegido, para cada tipo de alimentación disponible.
        El gabinete seleccionado se resalta en color, y las líneas se trazan de borde
        a borde entre los rectángulos, facilitando la lectura del esquema.
        </p>

        <h2>7. Redimensionamiento y tablas</h2>

        <p>
        La ventana principal puede maximizarse y redimensionarse libremente. Las diferentes
        pestañas se adaptan al tamaño de la ventana, y las tablas permiten ajustar el
        ancho de sus columnas arrastrando el borde del encabezado.
        </p>

        <div class="panel">
            <b>Recomendación:</b> cuando trabajes con muchos gabinetes y columnas
            (especialmente en la pestaña de Alimentación tableros), es conveniente
            maximizar la ventana para ver la mayor cantidad de información posible
            sin necesidad de barras de desplazamiento.
        </div>

        <h2>8. Base de datos de componentes</h2>

        <p>
        Desde el menú <b>Herramientas → Base de datos de componentes…</b> se abre una
        ventana independiente donde puedes:
        </p>
        <ul>
            <li>Agregar nuevos modelos de equipos.</li>
            <li>Modificar potencias, tipo de consumo, fase, origen, etc.</li>
            <li>Eliminar registros que ya no se utilicen.</li>
        </ul>

        <p>
        Esta base de datos es la fuente de información para la lista de “Componentes”
        que aparece en la pestaña <b>Componentes</b>. Mantenerla actualizada simplifica
        la selección de equipos y reduce errores de tipeo.
        </p>

        <h2>9. Buenas prácticas generales</h2>

        <ul>
            <li>Guarda el proyecto con frecuencia, especialmente después de grandes cambios.</li>
            <li>Completa primero la estructura de salas y gabinetes, luego los componentes
                y finalmente la alimentación de tableros.</li>
            <li>Utiliza descripciones claras en gabinetes y componentes para facilitar
                la revisión posterior.</li>
            <li>Revisa el grafo de dependencias para detectar cadenas extrañas o tableros
                desconectados.</li>
            <li>Mantén la base de datos de componentes ordenada y sin duplicados innecesarios.</li>
        </ul>

        <h2>10. Manual en PDF</h2>

        <p>
        Si lo prefieres, puedes consultar el manual en formato PDF (ideal para imprimir
        o compartir con otros miembros del equipo):<br>
        <a href='Manual_Usuario_Servicios_Auxiliares.pdf'>Abrir manual en PDF</a>
        </p>

        <hr>
        <p style="color:#7f8c8d;">© 2025 – Calculadora de Bancos de Baterías</p>

        </body>
        </html>
        """
