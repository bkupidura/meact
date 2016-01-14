<script id="mapOnlineTemplate" type="x-handlebars-template">
    Board: {{name}}<br />
    seen: {{UpdateToSec last_update}}<br />
    {{#data}}
        {{0}}: {{1}}<br />
    {{/data}}
</script>
<script id="mapOfflineTemplate" type="x-handlebars-template">
    Board: {{name}}<br />
    Offline
</script>
<script id="nodeTemplate" type="x-handlebars-template">
    <h3>Nodes</h3>
    {{#each this}}
        {{#if data}}
            <h4>
                <button class="btn btn-primary btn-xs" onclick="showCommandDialog('{{name}}')">
                    {{desc}} ({{name}})
                </button>
            </h4>
            <h5>
                <span class="label label-default">seen: {{UpdateToSec last_update}}</span>&nbsp;
                {{#data}}
                    <span class="label label-info">{{0}}: {{1}}</span>&nbsp;
                {{/data}}
            </h5>
        {{else}}
            <h4>
                <button class="btn btn-danger btn-xs disabled">
                    {{desc}} ({{name}})
                </button>
            </h4>
        {{/if}}
    {{/each}}
</script>
<script id="statusServiceTemplate" type="x-handlebars-template">
    <h3>Service status</h3>
    <div class="status-wrapper">
        <div class="row">
            <h4>
            {{#each this}}
                <div class="col-sm-4 margin">{{@key}}</div>
                <div class="col-sm-8 margin">
                <div class="btn-group btn-toggle">
                {{#if this}}
                <button class="btn btn-general btn-xs" onclick="invertStatus('{{@key}}', '{{this}}')">
                    Off
                </button>
                <button class="btn btn-success btn-xs active" onclick="invertStatus('{{@key}}', '{{this}}')">
                    On
                </button>
                {{else}}
                <button class="btn btn-warning btn-xs active" onclick="invertStatus('{{@key}}', '{{this}}')">
                    Off
                </button>
                <button class="btn btn-general btn-xs" onclick="invertStatus('{{@key}}', '{{this}}')">
                    On
                </button>
                {{/if}}
                </div>
                </div>
           {{/each}}
            </h4>
        </div>
    </div>
</script>
<script id="statusStatusTemplate" type="x-handlebars-template">
    <h3>Status</h3>
    <div class="status-wrapper">
        <div class="row">
            <h4>
            {{#each this}}
                <div class="col-sm-4 margin">{{@key}}</div>
                <div class="col-sm-8 margin">
                <div class="btn-group btn-toggle">
                {{#if this}}
                <button class="btn btn-general btn-xs" onclick="invertStatus('{{@key}}', '{{this}}')">
                    False
                </button>
                <button class="btn btn-success btn-xs active" onclick="invertStatus('{{@key}}', '{{this}}')">
                    True
                </button>
                {{else}}
                <button class="btn btn-warning btn-xs active" onclick="invertStatus('{{@key}}', '{{this}}')">
                    False
                </button>
                <button class="btn btn-general btn-xs" onclick="invertStatus('{{@key}}', '{{this}}')">
                    True
                </button>
                {{/if}}
                </div>
                </div>
           {{/each}}
            </h4>
        </div>
    </div>
</script>
