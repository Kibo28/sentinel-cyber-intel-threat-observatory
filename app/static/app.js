'use strict';
const $=id=>document.getElementById(id);
const state={section:'home',items:[],stats:null,sources:null,severity:'All',query:'',tag:'',favorites:{},favoriteChanges:0,loading:false,refreshPending:false,seenChange:null};
const categories=['Cyberattacks','Vulnerabilities','Data Breaches','Ransomware','Technology'];
const opts={year:'numeric',month:'short',day:'numeric'};
function node(tag,cl='',text){let x=document.createElement(tag);if(cl)x.className=cl;if(text!==undefined&&text!==null)x.textContent=String(text);return x}
function append(parent,...children){children.filter(Boolean).forEach(c=>parent.appendChild(c));return parent}
function textdate(value){if(!value)return 'Unknown';let date=new Date(value);return Number.isNaN(date.getTime())?String(value):date.toLocaleDateString('en-GB',opts)}
function urlSafe(raw){try{let u=new URL(raw);return ['https:','http:'].includes(u.protocol)?u.href:''}catch{return ''}}
function link(url,label){let href=urlSafe(url);if(!href)return node('span','fine','Source link unavailable');let a=node('a','sourcea',label||new URL(href).hostname);a.href=href;a.target='_blank';a.rel='noopener noreferrer';return a}
function pill(level){let c=['Critical','High','Medium','Info'].includes(level)?level:'Info';return node('span','tag '+c,c)}
function makeButton(label,handler,cl='outlinebtn'){let b=node('button',cl,label);b.type='button';b.addEventListener('click',handler);return b}
function showToast(message){let x=$('toast');x.textContent=message;x.hidden=false;clearTimeout(showToast.t);showToast.t=setTimeout(()=>x.hidden=true,4200)}
function setTheme(mode){document.documentElement.dataset.theme=mode;try{localStorage.setItem('cti-theme',mode)}catch{};$('theme-btn').textContent=mode==='dark'?'☀':'☾';$('theme-btn').title='Switch to '+(mode==='dark'?'light':'dark')+' mode';$('theme-btn').setAttribute('aria-label',$('theme-btn').title);$('theme-btn').setAttribute('aria-pressed',mode==='dark'?'true':'false')}
function loadTheme(){let value;try{value=localStorage.getItem('cti-theme')}catch{};setTheme(value==='light'||value==='dark'?value:((window.matchMedia&&window.matchMedia('(prefers-color-scheme:dark)').matches)?'dark':'light'))}
async function api(path,opt){let resp=await fetch(path,opt);if(!resp.ok){let body;try{body=await resp.json()}catch{};let detail=body?.detail;throw new Error(Array.isArray(detail)?detail.map(error=>error.msg).join('; '):detail||`${resp.status}: ${resp.statusText}`)}return resp.json()}
async function refresh(force=false) {
    if (state.loading) {
        state.refreshPending ||= force;
        return;
    }
    state.loading = true;
    try {
        const favoriteChanges = state.favoriteChanges;
        const [stats, sources, {favorites}] = await Promise.all([
            api('/api/stats'), api('/api/sources'), api('/api/favorites'),
        ]);
        const previous = state.stats;
        if (force || !previous || stats.last_change_id !== previous.last_change_id) {
            const items = [];
            do {
                const page = await api(`/api/incidents?limit=2000&offset=${items.length}`);
                items.push(...page.items);
                if (page.items.length < 2000) break;
            } while (items.length < stats.total);
            state.items = items;
        }
        if (state.seenChange === null) {
            let saved = null;
            try { saved = localStorage.getItem('cti-seen-change'); } catch {}
            const cursor = Number(saved);
            if (saved === null || !Number.isSafeInteger(cursor) || cursor < 0 || cursor > stats.last_change_id) {
                saveSeen(stats.last_change_id);
            } else {
                state.seenChange = cursor;
            }
        }
        const favoritesChanged = favoriteChanges === state.favoriteChanges && JSON.stringify(favorites) !== JSON.stringify(state.favorites);
        if (favoritesChanged) state.favorites = favorites;
        const changed = favoritesChanged || JSON.stringify(stats) !== JSON.stringify(previous) || JSON.stringify(sources) !== JSON.stringify(state.sources);
        state.stats = stats;
        state.sources = sources;
        syncStatus();
        updateNewBadge();
        if (force || changed) render();
        if (previous && stats.last_change_id > previous.last_change_id && unreadItems().length) {
            showToast(`${unreadItems().length} unread findings or updates`);
        }
    } catch (error) {
        showToast('Unable to read observatory: ' + error.message);
    } finally {
        state.loading = false;
        if (state.refreshPending) {
            state.refreshPending = false;
            void refresh(true);
        }
    }
}
function syncStatus(){let s=state.stats||{};let running=!!s.sync_running;$('status-dot').classList.toggle('warn',running);$('status-title').textContent=running?'Synchronizing feeds':'Local observatory active';let date=s.last_run?.completed;let text=$('status-detail');text.textContent=running?'Collecting source updates':date?'Last check '+textdate(date):'No completed sync yet';$('sync-state').textContent=running?'● SYNC IN PROGRESS':'● CYBER INTEL OBSERVATORY';$('sync-btn').disabled=running}
function head(title,kicker,subtitle){let top=node('div','pagehead'),l=node('div');append(l,node('div','eyebrow',kicker),node('h1','',title),node('p','',subtitle));append(top,l,node('div','datepill','⌁ '+new Date().toLocaleDateString('en-GB',{weekday:'long',day:'numeric',month:'long',year:'numeric'})));return top}
function panel(title,caption){let p=node('section','panel'),h=node('div','panelhead');append(h,node('h2','',title),node('small','',caption));append(p,h);return p}
function summaryText(item){return (item.summary||'No summary available. Open the authoritative source for details.').slice(0,550)}
function recordRow(item, compact=false) {
    const row = node('div', compact ? 'rowitem' : 'item');
    const left = node('div', compact ? 'rowmain' : 'itemtext');
    const meta = node('div', 'itemmeta');
    append(meta, pill(item.severity), node('span', '', `${item.category}  ·  ${item.source_name || 'Imported'}  ·  ${textdate(item.published_at || item.first_seen)}`));
    const tags = state.favorites[item.id];
    if (tags) {
        const star = node('span', 'favorite-star', '★');
        star.setAttribute('role', 'img');
        star.setAttribute('aria-label', 'In favorites');
        meta.prepend(star);
    }
    append(left, meta, node(compact ? 'strong' : 'h3', '', item.title));
    if (!compact) append(left, node('p', '', summaryText(item)));
    else append(left, node('span', 'fine', item.cve ? item.cve + '  ·  ' + (item.confidence || '') : (item.confidence || '')));
    const labels = Object.values(tags || {});
    if (labels.length) append(left, append(node('div', 'favorite-tags'), ...labels.map(name => node('span', 'favorite-tag', name))));

    const right = node('div', 'itemactions');
    if (item.change_id > state.seenChange) append(right, node('span', 'new-badge', item.updates ? 'New activity' : 'New'));
    if (item.updates) append(right, node('span', 'tag update', `↻ ${item.updates} update${item.updates > 1 ? 's' : ''}`));
    append(right, makeButton('View details', () => openDetail(item.id)));
    return append(row, left, right);
}
function renderHome(){let root=$('main');append(root,head('Cyber Intel · Threat Observatory','COMMAND CENTER','A unified local view of security reporting, vulnerabilities and incident history.'));
let stat=state.stats||{};let nums=[['Total records',stat.total||0,'Retained across daily runs',''],['Exploited / High+',((stat.severities?.Critical||0)+(stat.severities?.High||0)),'Severity is triage, not CVSS','warn'],['Vulnerabilities',stat.categories?.Vulnerabilities||0,'CISA KEV + research feeds','gold'],['Data breaches',stat.categories?.['Data Breaches']||0,'Reports require independent confirmation','blue']];let metric=node('div','metrics');nums.forEach(([label,n,foot,cl])=>{let m=node('div','metric '+cl);append(m,node('div','metriclabel',label),node('div','metricnum',n),node('div','metricfoot',foot));metric.appendChild(m)});root.appendChild(metric);
const rec = homeRecords(root);
let grid=node('div','gridtwo');
let right=node('div');let trend=panel('Threat categories','Distribution');let body=node('div','panelbody');let total=Math.max(1,stat.total||0);categories.forEach(c=>{let count=stat.categories?.[c]||0;let s=node('div','signal'),inner=node('div');inner.style.flex='1';append(inner,node('div','signalname',c));let bar=node('div','bar'),fill=node('span');fill.style.width=(count/total*100)+'%';append(bar,fill);inner.appendChild(bar);append(s,inner,node('span','signalcount',count));body.appendChild(s)});trend.appendChild(body);
let summary=panel('Collection status',scheduleLabel(stat));let info=node('div','panelbody');let date=stat.last_run?.completed;append(info,node('p','smalltext muted',date?('Last completed: '+textdate(date)):'No completed feed check recorded.'),node('p','smalltext muted',`Latest run: ${stat.last_run?.new_items??0} new, ${stat.last_run?.updates??0} material updates, ${stat.last_run?.duplicates??0} duplicates skipped.`),node('p','fine','The sources report articles or advisories; this dashboard does not independently verify incident claims or exploitability.'),makeButton('Collection settings',openSettings));summary.appendChild(info);right.appendChild(trend);right.appendChild(node('div','loose'));right.appendChild(summary);append(grid,rec,right);root.appendChild(grid);
let banner=node('div','notice');append(banner,node('strong','','Deduplication active. '),node('span','','Matching CVEs, article URLs and near-identical headlines are combined. Major CISA exploitation confirmations appear in the record’s update timeline.'));root.appendChild(banner)}
function empty(title,detail){let d=node('div','empty');append(d,node('strong','',title),node('span','',detail));return d}
function homeRecords(root) {
    const card = panel('Latest intelligence', 'Newest collected records');
    card.id = 'home-records';
    const title = card.querySelector('h2');
    const caption = card.querySelector('small');
    caption.setAttribute('role', 'status');
    const list = node('div', 'itemlist');
    card.appendChild(list);

    const update = () => {
        const searching = Boolean(state.query.trim());
        const matches = filterItems('All');
        const records = searching ? matches : matches.slice(0, 8);
        title.textContent = searching ? 'Search results' : 'Latest intelligence';
        caption.textContent = searching ? `${records.length} ${records.length === 1 ? 'finding' : 'findings'}` : 'Newest collected records';
        list.replaceChildren();
        if (records.length) {
            records.forEach(record => list.appendChild(recordRow(record)));
        } else {
            list.appendChild(searching
                ? empty('No matching intelligence', 'Try a different keyword, vendor, or CVE.')
                : empty('No incidents collected yet', 'The first synchronization runs automatically on startup. You can also click Sync feeds.'));
        }
    };
    const input = searchInput(update);
    input.setAttribute('aria-controls', card.id);
    const bar = node('div', 'filterrow home-search');
    bar.setAttribute('role', 'search');
    root.appendChild(append(bar, input));
    update();
    return card;
}
function renderCategory(){let root=$('main'),key=state.section;append(root,head(key,'INTELLIGENCE / '+key.toUpperCase(),key==='Vulnerabilities'?'CVEs, active exploitation, advisories and vulnerability research.':'Latest source-attributed findings in this intelligence category.'));renderFeed(root,key)}
function filterItems(cat, records=state.items) {
    const query = state.query.trim().toLowerCase();
    return records.filter(item =>
        (cat === 'All' || item.category === cat) &&
        (state.severity === 'All' || item.severity === state.severity) &&
        (!query || [item.title, item.summary, item.cve, item.source_name, item.vendor, ...Object.values(state.favorites[item.id] || {})]
            .some(value => String(value || '').toLowerCase().includes(query)))
    ).sort((a, b) => (b.first_seen || '').localeCompare(a.first_seen || ''));
}
function searchInput(onChange, placeholder='Search incidents, vendors, CVEs…', label='Search records') {
    const input = node('input', 'search');
    input.type = 'search';
    input.placeholder = placeholder;
    input.value = state.query;
    input.setAttribute('aria-label', label);
    input.addEventListener('input', () => {
        state.query = input.value;
        onChange();
    });
    return input;
}
function favoriteTagOptions() {
    const tags = new Map();
    for (const recordTags of Object.values(state.favorites)) {
        for (const [key, name] of Object.entries(recordTags)) {
            if (!tags.has(key)) tags.set(key, name);
        }
    }
    return [...tags].sort((a, b) => a[1].localeCompare(b[1]));
}

function renderFavorites() {
    const root = $('main');
    append(root, head('Favorites', 'INTELLIGENCE / SAVED', 'Find saved records by keyword or tag.'));
    const saved = state.items.filter(item => Object.hasOwn(state.favorites, item.id));
    if (!saved.length) {
        append(root, empty('No favorites yet', 'Open a record and choose Add to favorites.'));
        return;
    }

    const options = favoriteTagOptions();
    if (!options.some(([key]) => key === state.tag)) state.tag = '';
    const filter = selectInput([['', 'All tags'], ...options], state.tag);
    filter.setAttribute('aria-label', 'Filter by tag');
    filter.addEventListener('change', () => {
        state.tag = filter.value;
        updateResults();
    });
    const card = panel('Saved records', '');
    const count = card.querySelector('small');
    count.setAttribute('role', 'status');
    const list = node('div', 'itemlist');
    const bar = node('div', 'filterrow');
    bar.setAttribute('role', 'search');
    const search = searchInput(updateResults, 'Search favorites or tags…', 'Search favorites');
    const label = append(node('label', 'filterbuttons favorite-filter'), node('span', 'fine', 'Tag'), filter);
    append(root, append(bar, search, label), append(card, list));
    updateResults();

    function updateResults() {
        const matches = filterItems('All', saved).filter(item =>
            !state.tag || Object.hasOwn(state.favorites[item.id], state.tag));
        count.textContent = `${matches.length} ${matches.length === 1 ? 'record' : 'records'}`;
        list.replaceChildren();
        if (matches.length) matches.forEach(item => list.appendChild(recordRow(item)));
        else append(list, empty('No matching favorites', 'Try a different search or choose another tag.'));
    }
}

function filterbar(root,cat){let wrap=node('div','filterrow');let input=searchInput(render);let filter=node('div','filterbuttons');let label=node('span','fine','Severity');let select=node('select');['All','Critical','High','Medium','Info'].forEach(x=>{let op=node('option','',x);op.value=x;select.appendChild(op)});select.value=state.severity;select.addEventListener('change',()=>{state.severity=select.value;render()});append(filter,label,select);if(cat==='All')append(filter,makeButton('CSV ↧',()=>window.location.href='/api/export.csv'));
append(wrap,input,filter);root.appendChild(wrap)}
function renderFeed(root,cat){filterbar(root,cat);let items=filterItems(cat);let card=panel('Intelligence records',items.length+' findings');let list=node('div','itemlist');if(items.length)items.forEach(x=>list.appendChild(recordRow(x)));else list.appendChild(empty('No matching intelligence','Try a broader search or run Sync feeds to retrieve new records.'));card.appendChild(list);root.appendChild(card)}
function renderHistory(){let root=$('main');append(root,head('Incident history','ARCHIVE / PERMANENT RECORD','Search the complete archive by incident, date, product or CVE. Click a record for its sources and update timeline.'));filterbar(root,'All');let items=filterItems('All'),grouped=new Map();items.forEach(x=>{let k=(x.first_seen||'Unknown').slice(0,10);if(!grouped.has(k))grouped.set(k,[]);grouped.get(k).push(x)});if(!items.length){root.appendChild(empty('History is empty','Once feeds are synchronized, every new record remains available here.'));return}for(let [day,rows] of grouped){let d=node('div','historydate',textdate(day)+' · '+rows.length+' records');root.appendChild(d);let card=node('div','historygroup');rows.forEach(x=>card.appendChild(recordRow(x,true)));root.appendChild(card)}let note=node('div','notice');append(note,node('strong','','Incident history is persistent. '),node('span','','Your SQLite archive is stored in the Docker data volume; browser cache clearing does not delete it.'));root.appendChild(note)}
function renderSources() {
    const root = $('main');
    append(root, head('Intelligence sources', 'COLLECTION / TRANSPARENCY', 'Manage automated feeds and link-only research sources.'));
    if (!state.sources) {
        root.appendChild(empty('Loading sources', 'The configured sources will appear here.'));
        return;
    }
    const card = panel('Automated sources', 'RSS, Atom and CISA KEV');
    const table = node('table', 'source-table');
    const header = node('tr');
    ['Source', 'Type', 'Status', 'Last check', 'Actions'].forEach(label => {
        const cell = node('th', '', label);
        cell.scope = 'col';
        header.appendChild(cell);
    });
    table.appendChild(header);
    for (const [index, source] of state.sources.feeds.entries()) {
        const row = node('tr');
        const sourceCell = append(node('td'), link(source.url, source.name), node('div', 'src-info', source.mode));
        const status = source.enabled ? source.status?.status : 'disabled';
        const label = {ok: `OK · ${source.status?.fetched ?? 0} items`, error: 'Fetch error', disabled: 'Disabled'}[status] || 'Pending';
        const edit = source.mode === 'JSON' ? () => editBuiltIn('kev_enabled', 'CISA KEV') : () => editSource('feeds', index);
        append(row, sourceCell, node('td', '', source.type), node('td', status === 'error' ? 'bad' : status || 'muted', label),
            node('td', '', source.status?.last_checked ? textdate(source.status.last_checked) : '—'),
            append(node('td'), makeButton('Edit', edit)));
        table.appendChild(row);
        if (status === 'error') {
            const detail = node('td', 'fine', source.status.details);
            detail.colSpan = 5;
            table.appendChild(append(node('tr'), detail));
        }
    }
    append(card, append(node('div', 'panelbody table-scroll'), table,
        makeButton('Add RSS / Atom feed', () => editSource('feeds'))));
    root.appendChild(card);

    const external = panel('Research links', 'Links open in your browser');
    const body = node('div', 'panelbody');
    state.sources.config.external.forEach((source, index) => {
        const description = append(node('div'), link(source.url, source.name), node('div', 'src-info', source.note));
        body.appendChild(append(node('div', 'source-edit-row'), description, makeButton('Edit', () => editSource('external', index))));
    });
    append(body, makeButton('Add research link', () => editSource('external')));
    append(external, body);
    external.classList.add('loose');
    root.appendChild(external);

    const enrichment = panel('EPSS enrichment', 'Exploitation probability');
    append(enrichment, append(node('div', 'panelbody source-edit-row'),
        node('span', 'fine', state.sources.config.epss_enabled ? 'FIRST EPSS enabled' : 'FIRST EPSS disabled'),
        makeButton('Edit', () => editBuiltIn('epss_enabled', 'FIRST EPSS'))));
    enrichment.classList.add('loose');
    root.appendChild(enrichment);
}
function render() {
    const root = $('main');
    const focused = document.activeElement;
    const searchFocused = focused?.matches('input.search') && root.contains(focused);
    root.replaceChildren();
    $('crumb-title').textContent = state.section === 'home' ? 'OVERVIEW' : state.section.toUpperCase();
    document.querySelectorAll('[data-section]').forEach(button => {
        button.classList.toggle('active', button.dataset.section === state.section);
    });
    if (state.section === 'home') renderHome();
    else if (state.section === 'history') renderHistory();
    else if (state.section === 'sources') renderSources();
    else if (state.section === 'new') renderNew();
    else if (state.section === 'favorites') renderFavorites();
    else renderCategory();
    const search = searchFocused && root.querySelector('input.search');
    if (search) {
        search.focus({preventScroll: true});
        search.setSelectionRange(focused.selectionStart, focused.selectionEnd, focused.selectionDirection);
    }
}
function navigate(section){state.section=section;state.query='';state.severity='All';state.tag='';$('sidebar').classList.remove('show');render();window.scrollTo({top:0,behavior:'auto'})}
function favoriteControls(record) {
    let organization = record.organization;
    const section = node('section', 'favorite-controls');
    const toggle = makeButton('', () => save({favorite: !organization.favorite}, toggle));
    const tagEditor = node('div');
    const tags = node('div', 'favorite-tags');
    const form = node('form', 'favorite-tag-form');
    const input = inputField('text', '', 40);
    input.id = 'favorite-tag';
    input.required = true;
    input.setAttribute('list', 'favorite-tag-suggestions');
    input.placeholder = 'Add a tag…';
    const label = node('label', 'fine', 'Tags');
    label.htmlFor = input.id;
    const suggestions = node('datalist');
    suggestions.id = 'favorite-tag-suggestions';
    const add = node('button', 'outlinebtn', 'Add tag');
    add.type = 'submit';
    form.addEventListener('submit', event => {
        event.preventDefault();
        input.value = input.value.trim();
        if (input.reportValidity()) void save({add_tag: input.value}, input);
    });
    append(section, toggle, append(tagEditor, label, tags, append(form, input, add, suggestions)));
    renderControls();
    return section;

    function renderControls() {
        toggle.textContent = organization.favorite ? '★ Remove from favorites' : '☆ Add to favorites';
        tagEditor.hidden = !organization.favorite;
        tags.replaceChildren(...Object.values(organization.tags).map(name => {
            const button = makeButton(`${name} ×`, () => save({remove_tag: name}, input), 'favorite-tag');
            button.setAttribute('aria-label', `Remove tag ${name}`);
            return button;
        }));
        suggestions.replaceChildren(...favoriteTagOptions()
            .filter(([key]) => !Object.hasOwn(organization.tags, key))
            .map(([, name]) => {
                const option = node('option');
                option.value = name;
                return option;
            }));
    }

    async function save(change, focusTarget) {
        if (toggle.disabled) return;
        const controls = section.querySelectorAll('button, input');
        controls.forEach(control => { control.disabled = true; });
        try {
            organization = await api(`/api/incidents/${encodeURIComponent(record.id)}/organization`, {
                method: 'PATCH',
                headers: {'Content-Type': 'application/json', 'X-CTI-Request': 'dashboard'},
                body: JSON.stringify(change),
            });
            state.favoriteChanges++;
            if (organization.favorite) state.favorites[record.id] = organization.tags;
            else delete state.favorites[record.id];
            if (change.add_tag) input.value = '';
            renderControls();
            render();
        } catch (error) {
            showToast('Unable to save favorites: ' + error.message);
        } finally {
            controls.forEach(control => { control.disabled = false; });
            if (section.isConnected && !$('detaildrawer').hidden) focusTarget.focus({preventScroll: true});
        }
    }
}

function detailField(label,value){let d=node('div','detailbox');append(d,node('small','',label),node('b','',String(value===null||value===undefined||value===''?'Not established':value)));return d}
async function openDetail(id){try{let d=await api('/api/incidents/'+encodeURIComponent(id)),root=$('drawer-body');root.replaceChildren();append(root,pill(d.severity),node('span','sourcepill',d.category),node('h2','',d.title),node('div','fine','Record ID: '+d.id),favoriteControls(d));let info=node('div','detailgrid');[['Confidence',d.confidence],['Original publication',textdate(d.published_at)],['Collected on',textdate(d.first_seen)],['Last observed',textdate(d.last_seen)],['Region',d.region],['Evidence source',d.source_name],['CVE',d.cve||'Not applicable'],['Actively exploited',d.exploited?'Listed in CISA KEV':'Not established'],['CVSS',d.cvss||'Not available from source'],['EPSS probability',d.epss_score==null?'Not retrieved':(d.epss_score*100).toFixed(2)+'%'],['Vendor',d.vendor||'Unknown'],['Affected versions',d.affected_versions||'Consult vendor advisory']].forEach(([k,v])=>info.appendChild(detailField(k,v)));root.appendChild(info);
append(root,node('div','sectionlabel','SUMMARY / IMPACT'),node('p','prose',summaryText(d)));
root.appendChild(shareActions(d));
append(root,node('div','sectionlabel','MITIGATION / NEXT ACTION'),node('p','prose',d.remediation||'Review the primary source and assess exposure; avoid relying on headlines alone.'));
let s=node('div','sectionlabel','SOURCE DOCUMENTS');root.appendChild(s);let sources=node('div','sourceslist');(d.sources||[]).forEach(x=>sources.appendChild(link(x.url,x.name||x.url)));if(!(d.sources||[]).length)sources.appendChild(node('span','muted','No source URL stored.'));root.appendChild(sources);
root.appendChild(node('div','sectionlabel','EVENT HISTORY'));let timeline=node('div','timeline');(d.history||[]).forEach(change=>{let row=node('div','timelineitem');append(row,node('small','',textdate(change.change_at)),node('span','',change.description));timeline.appendChild(row)});root.appendChild(timeline);
$('detaildrawer').hidden=false;$('drawer-backdrop').hidden=false;$('drawer-close').focus()}catch(e){showToast('Cannot open record: '+e.message)}}
function closeDetail(){$('detaildrawer').hidden=true;$('drawer-backdrop').hidden=true}
async function manualSync(){try{let result=await api('/api/sync',{method:'POST',headers:{'X-CTI-Request':'dashboard'}});showToast(result.status==='queued'?'Feed synchronization started.':'A synchronization is already in progress.');setTimeout(refresh,900);setTimeout(refresh,7000)}catch(e){showToast('Sync request: '+e.message)}}
async function handleImport(e){let f=e.target.files?.[0];if(!f)return;try{if(f.size>15_000_000)throw new Error('Import file over 15MB');let payload=JSON.parse(await f.text());if(!Array.isArray(payload)&&!Array.isArray(payload.items))throw new Error('Expected JSON with items array');let resp=await api('/api/import',{method:'POST',headers:{'Content-Type':'application/json','X-CTI-Request':'dashboard'},body:JSON.stringify(payload)});showToast(`Import finished: ${resp.new} added, ${resp.duplicate} duplicates skipped.`);await refresh()}catch(ex){showToast('Import failed: '+ex.message)}finally{e.target.value=''}}

function saveSeen(cursor) {
    state.seenChange = cursor;
    try { localStorage.setItem('cti-seen-change', String(cursor)); } catch {}
}

function unreadItems() {
    return state.items.filter(item => item.change_id > state.seenChange);
}

function updateNewBadge() {
    const count = unreadItems().length;
    $('new-count').textContent = count;
    $('new-count').hidden = count === 0;
}

function renderNew() {
    const root = $('main');
    append(root, head('New findings', 'INTELLIGENCE / UNREAD', 'New records and material updates since you last marked findings as seen in this browser.'));
    const items = unreadItems().sort((a, b) => b.change_id - a.change_id);
    if (!items.length) {
        root.appendChild(empty('You’re caught up', 'New activity will appear here after the next successful collection.'));
        return;
    }
    const actions = node('div', 'manage-actions');
    append(actions, makeButton('Mark all as seen', () => {
        saveSeen(items[0].change_id);
        updateNewBadge();
        render();
    }));
    const card = panel('Unread activity', `${items.length} findings`);
    const list = node('div', 'itemlist');
    items.forEach(item => list.appendChild(recordRow(item)));
    append(root, actions, append(card, list));
}

function scheduleLabel(settings) {
    const minutes = settings.interval_minutes;
    if (minutes) {
        if (minutes % 60 === 0) return `Every ${minutes / 60} ${minutes === 60 ? 'hour' : 'hours'}`;
        return `Every ${minutes} ${minutes === 1 ? 'minute' : 'minutes'}`;
    }
    const hour = String(settings.hour ?? 8).padStart(2, '0');
    const minute = String(settings.minute ?? 0).padStart(2, '0');
    return `Daily ${hour}:${minute} · ${settings.timezone || 'Europe/Zurich'}`;
}

function selectInput(values, selected) {
    const select = node('select');
    values.forEach(([value, label]) => {
        const option = node('option', '', label);
        option.value = value;
        select.appendChild(option);
    });
    select.value = selected;
    return select;
}

function checkInput(checked) {
    const input = node('input');
    input.type = 'checkbox';
    input.checked = checked;
    return input;
}

function inputField(type, value, maxLength) {
    const input = node('input');
    input.type = type;
    input.value = value;
    if (maxLength) input.maxLength = maxLength;
    return input;
}

function editField(label, input) {
    return append(node('label', input.type === 'checkbox' ? 'edit-check' : 'edit-field'), input.type === 'checkbox' ? input : node('span', '', label),
        input.type === 'checkbox' ? node('span', '', label) : input);
}

function editor(title, fields, onSave, onRemove) {
    const dialog = $('edit-dialog');
    const form = node('form', 'edit-form');
    const error = node('p', 'edit-error');
    error.setAttribute('role', 'alert');
    const actions = node('div', 'manage-actions');
    const save = node('button', 'btn btn-primary', 'Save');
    save.type = 'submit';
    const cancel = makeButton('Cancel', () => dialog.close());
    const submit = async task => {
        const buttons = [...actions.querySelectorAll('button')];
        buttons.forEach(button => { button.disabled = true; });
        error.textContent = '';
        try {
            await task();
            dialog.close();
            showToast('Changes saved');
            void refresh(true);
        } catch (ex) {
            error.textContent = ex.message;
        } finally {
            buttons.forEach(button => { button.disabled = false; });
        }
    };
    append(actions, save, cancel);
    if (onRemove) append(actions, makeButton('Remove source', () => {
        if (window.confirm('Remove this source? Its archived findings will be kept.')) void submit(onRemove);
    }));
    form.addEventListener('submit', event => {
        event.preventDefault();
        void submit(onSave);
    });
    append(form, ...fields, error, actions);
    $('edit-title').textContent = title;
    $('edit-body').replaceChildren(form);
    $('sidebar').classList.remove('show');
    dialog.showModal();
}

function updateConfig(path, payload) {
    return api(path, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json', 'X-CTI-Request': 'dashboard'},
        body: JSON.stringify(payload),
    });
}

function editSource(collection, index) {
    const config = state.sources.config;
    const source = config[collection][index];
    const feed = collection === 'feeds';
    const name = inputField('text', source?.name || '', 100);
    const url = inputField('url', source?.url || '', 2000);
    name.required = url.required = true;
    const fields = [editField('Name', name), editField(feed ? 'RSS / Atom URL' : 'Website URL', url)];
    const category = selectInput([['auto', 'Automatic'], ...categories.map(value => [value, value])], source?.category || 'auto');
    const type = selectInput([['news', 'News'], ['research', 'Research'], ['official', 'Official']], source?.source_type || 'news');
    const enabled = checkInput(source?.enabled ?? true);
    const note = inputField('text', source?.note || '', 400);
    if (feed) {
        fields.push(editField('Category', category), editField('Source type', type), editField('Include in feed refreshes', enabled));
    } else {
        fields.push(editField('Note', note));
    }
    const save = () => {
        const entry = {name: name.value.trim(), url: url.value.trim()};
        Object.assign(entry, feed ? {category: category.value, source_type: type.value, enabled: enabled.checked} : {note: note.value.trim()});
        const entries = [...config[collection]];
        if (source) entries[index] = entry;
        else entries.push(entry);
        return updateConfig('/api/sources', {...config, [collection]: entries});
    };
    const remove = source ? () => updateConfig('/api/sources', {...config, [collection]: config[collection].filter((_, i) => i !== index)}) : null;
    editor(source ? 'Edit source' : feed ? 'Add RSS / Atom feed' : 'Add research link', fields, save, remove);
}

function editBuiltIn(key, name) {
    const config = state.sources.config;
    const enabled = checkInput(config[key]);
    editor(name, [editField(`Enable ${name}`, enabled)], () => updateConfig('/api/sources', {...config, [key]: enabled.checked}));
}

function testEmailControls(available) {
    const status = node('span', 'fine');
    status.setAttribute('role', 'status');
    const button = makeButton('Send test email', async () => {
        button.disabled = true;
        status.classList.remove('bad');
        status.textContent = 'Sending to the configured recipients…';
        try {
            const {refused_recipients: refused} = await api('/api/settings/test-email', {
                method: 'POST', headers: {'X-CTI-Request': 'dashboard'},
            });
            status.textContent = refused
                ? `The SMTP server accepted the test email and rejected ${refused} ${refused === 1 ? 'recipient' : 'recipients'}.`
                : 'The SMTP server accepted the test email. Check the configured inboxes.';
        } catch (error) {
            status.classList.add('bad');
            status.textContent = error.message;
        } finally {
            button.disabled = false;
        }
    });
    button.disabled = !available;
    return append(node('div', 'manage-actions'), button, status);
}

async function openSettings() {
    try {
        const settings = await api('/api/settings');
        if ($('edit-dialog').open) return;
        const interval = settings.interval_minutes;
        const useHours = interval && interval % 60 === 0;
        const schedule = selectInput([['daily', scheduleLabel({...settings, interval_minutes: null})], ['interval', 'Repeat at an interval']], interval ? 'interval' : 'daily');
        const units = selectInput([['minutes', 'Minutes'], ['hours', 'Hours']], useHours ? 'hours' : 'minutes');
        const amount = inputField('number', useHours ? interval / 60 : interval || 60);
        amount.min = '1';
        amount.step = '1';
        amount.required = true;
        const range = node('p', 'fine', 'Choose 1–1,440 minutes or 1–24 hours between refreshes. Sync feeds is always available for an immediate refresh.');
        const duration = append(node('div', 'edit-duration'), editField('Repeat every', amount), editField('Unit', units), range);
        const syncFields = () => {
            duration.hidden = schedule.value !== 'interval';
            amount.disabled = duration.hidden;
            amount.max = units.value === 'hours' ? '24' : '1440';
        };
        schedule.addEventListener('change', syncFields);
        units.addEventListener('change', () => {
            if (units.value === 'hours') amount.value = Math.max(1, Math.round(amount.valueAsNumber / 60) || 1);
            else amount.value = amount.valueAsNumber * 60 || 60;
            syncFields();
        });
        syncFields();
        const email = checkInput(settings.email_enabled);
        email.disabled = !settings.email_available && !settings.email_enabled;
        const smtp = settings.email_available ? 'A digest goes to the SMTP recipients configured on the NAS when a refresh finds new activity.' : 'Configure SMTP in the NAS .env file to enable email alerts.';
        const fields = [editField('Refresh schedule', schedule), duration, editField('Email new findings and material updates', email),
            node('p', 'fine', smtp), testEmailControls(settings.email_available)];
        editor('Collection settings', fields, () => {
            const minutes = schedule.value === 'interval' ? amount.valueAsNumber * (units.value === 'hours' ? 60 : 1) : null;
            return updateConfig('/api/settings', {revision: settings.revision, interval_minutes: minutes, email_enabled: email.checked});
        });
    } catch (error) {
        showToast('Unable to open settings: ' + error.message);
    }
}

function shareActions(record) {
    const url = urlSafe(record.primary_url);
    const message = [record.title, `${record.severity} · ${record.category}`, summaryText(record), url].filter(Boolean).join('\n\n');
    const area = node('textarea', 'share-copy');
    area.value = message;
    area.readOnly = true;
    area.hidden = true;
    area.setAttribute('aria-label', 'Shareable finding summary');
    const copy = makeButton('Copy summary', async () => {
        try {
            if (!navigator.clipboard) throw new Error('Clipboard unavailable');
            await navigator.clipboard.writeText(message);
        } catch {
            area.hidden = false;
            area.focus();
            area.select();
            try {
                if (!document.execCommand('copy')) return;
            } catch {
                return;
            }
            area.hidden = true;
            copy.focus();
        }
        showToast('Summary copied');
    });
    const mail = node('a', 'outlinebtn', 'Email draft');
    const subject = record.title.replace(/[\r\n]+/g, ' ');
    mail.href = `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(message)}`;
    const actions = append(node('div', 'manage-actions'), copy, mail);
    if (navigator.share) append(actions, makeButton('Share…', async () => {
        try {
            await navigator.share({title: record.title, text: message});
        } catch (error) {
            if (error.name !== 'AbortError') showToast('Unable to share. You can copy the summary or open an email draft.');
        }
    }));
    return append(node('div'), actions, area);
}

const updateMessages = {
    disabled: 'Set up the NAS updater using the Synology installation guide to enable this button.',
    idle: 'Ready to check GitHub for an update.',
    queued: 'Update queued. The NAS will start it on the next scheduled check.',
    running: 'The NAS is building or restarting the dashboard. This may take a few minutes.',
    current: 'The dashboard is already on the latest version.',
    updated: 'Update complete. Reload the dashboard to open the new version.',
    failed: 'The update could not be completed. Check the NAS update task log for details.',
    rolled_back: 'The new version failed to start. The NAS restored the previous version.',
    rollback_failed: 'The update and rollback could not be verified. Check the NAS update task log.',
};
let updateRequestInFlight = false;

function showUpdateState(result) {
    const revision = result.revision ? ` Build ${result.revision.slice(0, 7)}.` : '';
    $('update-status').textContent = (updateMessages[result.state] || updateMessages.failed) + revision;
    $('update-start').disabled = ['disabled', 'queued', 'running', 'rollback_failed'].includes(result.state);
    $('update-reload').hidden = result.state !== 'updated';
}

async function refreshUpdate() {
    if (!$('update-dialog').open || updateRequestInFlight) return;
    updateRequestInFlight = true;
    try {
        showUpdateState(await api('/api/update'));
    } catch {
        $('update-start').disabled = true;
        $('update-status').textContent = 'Waiting to reconnect to the dashboard…';
    } finally {
        updateRequestInFlight = false;
    }
}

async function startUpdate() {
    if (updateRequestInFlight) return;
    updateRequestInFlight = true;
    $('update-start').disabled = true;
    try {
        showUpdateState(await api('/api/update', {
            method: 'POST', headers: {'X-CTI-Request': 'dashboard'},
        }));
    } catch (error) {
        $('update-status').textContent = error.message;
    } finally {
        updateRequestInFlight = false;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    loadTheme();
    document.querySelectorAll('[data-section]').forEach(button => button.addEventListener('click', () => navigate(button.dataset.section)));
    $('theme-btn').addEventListener('click', () => setTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'));
    $('import-btn').addEventListener('click', () => $('import-file').click());
    $('import-file').addEventListener('change', handleImport);
    $('sync-btn').addEventListener('click', manualSync);
    $('settings-btn').addEventListener('click', openSettings);
    $('update-app-btn').addEventListener('click', () => {
        $('sidebar').classList.remove('show');
        $('update-dialog').showModal();
        void refreshUpdate();
    });
    $('update-start').addEventListener('click', startUpdate);
    $('update-close').addEventListener('click', () => $('update-dialog').close());
    $('update-reload').addEventListener('click', () => window.location.reload());
    $('edit-close').addEventListener('click', () => $('edit-dialog').close());
    $('drawer-close').addEventListener('click', closeDetail);
    $('drawer-backdrop').addEventListener('click', closeDetail);
    $('menu-btn').addEventListener('click', () => $('sidebar').classList.toggle('show'));
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape' && !$('edit-dialog').open) closeDetail();
    });
    void refresh();
    setInterval(refresh, 30_000);
    setInterval(refreshUpdate, 3_000);
});
