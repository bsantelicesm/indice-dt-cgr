# Índice de dictámenes DT y CGR

![](https://img.shields.io/badge/status-active-green) ![](https://img.shields.io/badge/releases-automatic-blue)

Esta es una herramienta para hacer búsquedas sobre el dataset completo de documentación proveída por la Dirección del Trabajo y la Contraloría General de la República, ambos de Chile. Es posible cargar todos los dictámenes y ordinarios en tablas MySQL para búsqueda de jurisprudencia, análisis de texto, entre otros. Para cada institución se genera una tabla completa en formato .sql o .xlsx con todos los resultados de búsqueda en cada caso.

En los [Releases](https://github.com/bsantelicesm/indice-dt-cgr/releases) se realiza un índice completo mensual, obtenido el primer día del mes. Puedes usar el código fuente para generar tus propias descargas o incorporar la estructura en tus propios proyectos. Por el tamaño del dataset, se recomienda utilizar la versión .sql en un motor de base de datos como MySQL, PostgreSQL, o SQLite para mejor performance, mientras que el .xlsx es recomendado para búsquedas simples de texto.

## Contenidos de la tabla
**dt - Dirección del Trabajo**
- *id:* Identificador único para el script, sólo indica en qué orden fueron extraídos.
- *url:* URL para acceder al documento en la página de la DT.
- *branch:* dictamen u ordinario.
- *epigrafe:*  epígrafe del documento.
- *titulo:* número identificador del documento.
- *fecha:* fecha de emisión del documento.
- *abstract:* resumen corto del documento.
- *hidden_text:* palabras clave asociadas a la materia del documento.
- *body_text:* cuerpo completo del documento.
- *scraped_at* fecha y hora de levantamiento del documento.

**cgr - Contraloría General de la República**
- *_id:* Identificador del documento en la CGR.
- *carácter:* indica ordinal latino si el documento comparte id (bis, ter, etc.)
- *documento_completo:* cuerpo completo del documento.
- *complementado:* posee otros documentos relacionados a la misma materia.
- *destinatarios:* destinatario del documento.
- *reconsiderado_parcialmente:* Fue sujeto a reconsideración parcial por la CGR.
- *aplicado:* Se generan aplicaciones a los servicios considerados.
- *fuentes legales:* (WIP) fuentes consideradas en el documento, no funciona adecuadamente en la API de búsqueda.
- *confirmado:* fue reafirmado por otros recursos de la CGR.
- *fecha_documento:* fecha de emisión del documento.
- *reconsiderado:* Fue sujeto a reconsideración por la CGR.
- *relevante:* Ni idea!
- *descriptores:* Palabras clave asociadas a la materia del documento.
- *origen:* unidad de la CGR responsable del documento.
- *tipo:* (WIP) sólo dictámenes por ahora.
- *aclarado:* Fue solicitada aclaración a la CGR.
- *nuevo:* Es la primera generación del documento.
- *criterio:* genera o aplica jurisprudencia.
- *materia:* resumen del documento.
- *recurso_protección:* referencia recurso de protección si aplica.
- *boletin:* corresponde a un boletín ordinario.
- *reactivado:* Ni idea!
- *alterado:* Ni idea!
- *scraped_at:* Fecha y hora del levantamiento del documento.

## Disclaimer
No estoy asociado de ninguna manera con la Contraloría General de la República, la Dirección del Trabajo, o de ninguna institución del Gobierno de Chile. Esta información es de carácter referencial y experimental, y todo trabajo riguroso a partir de la misma debe ser validado por los medios oficiales de cada institución.
No soy abogado, soy ingeniero, toda la información es de carácter referencial y no representa asesoría ninguna en materia legal.
Toda la información expuesta es de carácter público y de libre acceso mediante los canales oficiales de la respectiva institución, presentada en un formato procesable digitalmente.

## Solicitudes y Contribuciones
Para solicitar cambios, corregir errores u otras consultas utilizar la pestaña [Issues](https://github.com/bsantelicesm/indice-dt-cgr/issues) para levantar un caso y proceder con el seguimiento.
