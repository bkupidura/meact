<script id="mapOnlineTemplate" type="x-handlebars-template">
    Board: {{name}}<br />
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
                <span style="cursor: pointer;" class="label label-default" onclick="showCommandDialog('{{name}}')">{{desc}} ({{name}})</span>
            </h4>
            <h5>
                {{#data}}
                    <span class="label label-info">{{0}}: {{1}}</span>&nbsp;
                {{/data}}
            </h5>
        {{else}}
            <h4>
                <span class="label label-danger">{{desc}} ({{name}})</span>
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
                <div class="col-sm-8 margin">{{@key}}</div>
                <div class="col-sm-4 margin">
                {{#if this}}
                    <span style="cursor: pointer;" class="label label-success" onclick="invertStatus('{{@key}}', '{{this}}')">Enabled</span>
                {{else}}
                    <span style="cursor: pointer;" class="label label-danger" onclick="invertStatus('{{@key}}', '{{this}}')">Disabled</span>
                {{/if}}
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
                <div class="col-sm-8 margin">{{@key}}</div>
                <div class="col-sm-4 margin">
                {{#if this}}
                    <span style="cursor: pointer;" class="label label-success" onclick="invertStatus('{{@key}}', '{{this}}')">True</span>
                {{else}}
                    <span style="cursor: pointer;" class="label label-danger" onclick="invertStatus('{{@key}}', '{{this}}')">False</span>
                {{/if}}
                </div>
           {{/each}}
            </h4>
        </div>
    </div>
</script>
