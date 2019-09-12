$(window).on('entity:map', function (e, data) {

    var map = data.map;

    var managementLayers = [{url: window.SETTINGS.urls.landedge_layer, name: tr('Land type'), id: 'land'},
                            {url: window.SETTINGS.urls.physicaledge_layer, name: tr('Physical type'), id: 'physical'},
                            {url: window.SETTINGS.urls.competenceedge_layer, name: tr('Competence'), id: 'competence'},
                            {url: window.SETTINGS.urls.signagemanagementedge_layer, name: tr('Signage management'), id: 'signagemanagement'},
                            {url: window.SETTINGS.urls.workmanagementedge_layer, name: tr('Work management'), id: 'workmanagement'}];
    managementLayers.map(function(el) {
        el.isActive = false;
        return el;
    })

    var colorspools = L.Util.extend({}, window.SETTINGS.map.colorspool);
    for (var i=0; i<managementLayers.length; i++) {
        var managementLayer = managementLayers[i];

        var style = L.Util.extend({clickable: false},
                                  window.SETTINGS.map.styles[managementLayer.id] || {});
        var layer = new L.ObjectsLayer(null, {
            modelname: managementLayer.name,
            style: style,
            onEachFeature: initLandLayer(managementLayer),
        });

        var colorspool = colorspools[managementLayer.id];
        var nameHTML = '';
        for (var j=0; j<4; j++) {
            nameHTML += ('<span style="color: '+ colorspool[j] + ';">|</span>');
        }
        nameHTML += ('&nbsp;' + managementLayer.name);
        map.layerscontrol.addOverlay(layer, nameHTML, tr('Land edges'));
    };
    map.on('layeradd', function(e){
        var options = e.layer.options || {'modelname': 'None'};
        for (var i=0; i<managementLayers.length; i++) {
            if (! managementLayers[i].isActive){
                if (options.modelname == managementLayers[i].name){
                    e.layer.load(managementLayers[i].url);
                    managementLayers[i].isActive = true;
                }
            }
        }
        $( "#mainmap" ).append($('<div id="landgraph"><a class="toggle" title="{% trans "Toggle land edge legend" %}">&nbsp;</a><h4>{% trans "Land" %}</h4><br>{% for category in legend %}<h6 style="color:{{ category.1 }};">{{ category.0 }}</h6>{% endfor %}</div>'))
    });

    function initLandLayer(layergroup) {
        return function (data, layer) {
            var idx = parseInt(data.properties.color_index, 10);
            if (isNaN(idx)) {
                console.warn("No proper 'color_index' properties in GeoJSON properties.");
                idx = 0;
            }
            var colorspool = colorspools[layergroup.id],
                color = colorspool[idx % colorspool.length];
            layer.setStyle({color: color});

            // Add label in the middle of the line
            if (data.properties.name && window.SETTINGS.map.showonline) {
                MapEntity.showLineLabel(layer, {
                    color: color,
                    text: data.properties.name,
                    title: layergroup.name,
                    className: 'landlabel ' + layergroup.id + ' ' + idx
                });
            }
        };
    }
});
$(window).
    <div id="landgraph">
        <a class="toggle" title="{% trans "Toggle land edge legend" %}">&nbsp;</a><h4>{% trans "Land" %}</h4><br>
        {% for category in legend %}
            <h6 style="color:{{ category.1 }};">{{ category.0 }}</h6>
        {% endfor %}
    </div>
    <script type="text/javascript">
        $(document).ready(function () {
            $('#landgraph a.toggle').click(function (e) {
                $('#landgraph').toggleClass('colapsed');
            });
        });
    </script>