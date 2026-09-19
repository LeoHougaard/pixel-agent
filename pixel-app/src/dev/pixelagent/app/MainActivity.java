package dev.pixelagent.app;

import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.*;
import android.provider.Settings;
import android.view.*;
import android.webkit.*;
import android.widget.*;
import org.json.*;
import java.io.*;
import java.lang.ref.WeakReference;
import java.util.HashMap;

public class MainActivity extends Activity {
    private static final String PERMISSION="com.termux.permission.RUN_COMMAND";
    private static final String PREFIX="/data/data/com.termux/files/usr/bin/";
    private static final String CONTROL="/data/data/com.termux/files/home/.local/share/pixel-agent/pixel-app-control.py";
    private static final String BASE="http://127.0.0.1:3773/";
    private static final int BG=Color.rgb(10,10,10), TEXT=Color.rgb(230,230,230), MUTED=Color.rgb(135,135,135);
    private static final int GREEN=Color.rgb(110,178,139), AMBER=Color.rgb(205,166,92);
    private static WeakReference<MainActivity> current=new WeakReference<>(null);
    private final Handler handler=new Handler(Looper.getMainLooper());
    private final HashMap<Integer,PendingIntent> pending=new HashMap<>();
    private FrameLayout content;
    private LinearLayout loading;
    private WebView web;
    private TextView statusText, stageText, elapsedText, heartbeatText;
    private View dot;
    private Button retry;
    private ProgressBar progress;
    private ValueCallback<Uri[]> fileChoice;
    private AlertDialog statusDialog;
    private int nextId=1, generation=1, idleMinutes=5;
    private boolean foreground, desiredRunning=true, pairPending, chatRequested, chatLoaded, statusPending;
    private boolean transportOkay=true, autoConnect=true, checkOnResume, restoring;
    private String phase="starting", stage="Starting Termux", failure="", restoreRoute;
    private String phoneControl="Not checked", details="";
    private long operationSince=SystemClock.elapsedRealtime(), lastReply, lastStatusPoll, lastWebCheck;
    private double heartbeatAt;
    private boolean busy;
    private boolean interactionPending=true;
    private boolean workspaceTools;
    private boolean projectPending;
    private String projectStage="", pendingProjectTitle;

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved); current=new WeakReference<>(this);
        getWindow().setStatusBarColor(BG); getWindow().setNavigationBarColor(BG);
        LinearLayout root=column(); root.setBackgroundColor(BG);
        root.setOnApplyWindowInsetsListener((view,insets)->{
            view.setPadding(0,insets.getSystemWindowInsetTop(),0,insets.getSystemWindowInsetBottom());
            return insets.consumeSystemWindowInsets();
        });
        LinearLayout bar=new LinearLayout(this); bar.setGravity(Gravity.CENTER_VERTICAL); bar.setPadding(dp(16),0,dp(4),0);
        dot=new View(this); bar.addView(dot,new LinearLayout.LayoutParams(dp(6),dp(6)));
        statusText=label("Starting",12,MUTED); statusText.setPadding(dp(8),0,0,0);
        bar.addView(statusText,new LinearLayout.LayoutParams(0,dp(44),1)); statusText.setGravity(Gravity.CENTER_VERTICAL);
        Button menu=button("\u22ee",()->openMenu()); menu.setTextSize(24); menu.setContentDescription("Agent menu");
        bar.addView(menu,new LinearLayout.LayoutParams(dp(44),dp(44))); root.addView(bar);
        View line=new View(this); line.setBackgroundColor(Color.rgb(30,30,30)); root.addView(line,new LinearLayout.LayoutParams(-1,dp(1)));
        content=new FrameLayout(this); root.addView(content,new LinearLayout.LayoutParams(-1,0,1)); createWeb();
        loading=column(); loading.setGravity(Gravity.CENTER); loading.setPadding(dp(32),0,dp(32),dp(60));
        progress=new ProgressBar(this); progress.setIndeterminateTintList(android.content.res.ColorStateList.valueOf(MUTED));
        loading.addView(progress,new LinearLayout.LayoutParams(dp(22),dp(22)));
        stageText=label(stage,16,TEXT); stageText.setGravity(Gravity.CENTER); stageText.setPadding(0,dp(22),0,dp(8)); loading.addView(stageText);
        elapsedText=label("0:00",13,MUTED); elapsedText.setGravity(Gravity.CENTER); loading.addView(elapsedText);
        heartbeatText=label("",12,MUTED); heartbeatText.setGravity(Gravity.CENTER); heartbeatText.setPadding(0,dp(12),0,dp(14)); loading.addView(heartbeatText);
        retry=button("Retry",()->startAgent()); loading.addView(retry); content.addView(loading,new FrameLayout.LayoutParams(-1,-1));
        setContentView(root);
        // Drop the verification thread left by v1. Future user-selected routes persist.
        if(getPreferences(MODE_PRIVATE).getInt("ui_version",0)<2)
            getPreferences(MODE_PRIVATE).edit().remove("route").putInt("ui_version",2).apply();
        ensureAccess();
    }
    private int dp(int n) { return Math.round(n*getResources().getDisplayMetrics().density); }
    private LinearLayout column() { LinearLayout v=new LinearLayout(this); v.setOrientation(LinearLayout.VERTICAL); return v; }
    private TextView label(String text,int size,int color) { TextView v=new TextView(this); v.setText(text); v.setTextSize(size); v.setTextColor(color); return v; }
    private Button button(String text,Runnable action) {
        Button b=new Button(this); b.setText(text); b.setAllCaps(false); b.setTextSize(14); b.setTextColor(TEXT);
        b.setMinWidth(0); b.setMinimumWidth(0); b.setPadding(dp(12),0,dp(12),0); b.setBackgroundColor(Color.TRANSPARENT);
        b.setStateListAnimator(null); b.setElevation(0); b.setOnClickListener(v->action.run()); return b;
    }
    private void choose(String title,String[] labels,java.util.function.IntConsumer action) {
        new AlertDialog.Builder(this).setTitle(title).setItems(labels,(d,n)->action.accept(n)).show();
    }
    private void confirm(String title,String message,String yes,Runnable action) {
        new AlertDialog.Builder(this).setTitle(title).setMessage(message).setNegativeButton("Cancel",null)
            .setPositiveButton(yes,(d,w)->action.run()).show();
    }
    private void openMenu() {
        boolean off=phase.equals("stopped");
        choose("Agent",new String[]{off?"Start":"Stop agent","Reconnect chat","Status","GitHub projects",workspaceTools?"Hide workspace tools":"Workspace tools","Settings","Repair"},n->{
            if(n==0) { if(off) startAgent(); else stopAgent(); }
            if(n==1) reconnect(); if(n==2) showStatus();
            if(n==3){projectPending=true;projectStage="Loading GitHub repositories";operationSince=SystemClock.elapsedRealtime();updateUi();send("projects",new String[]{"projects"});}
            if(n==4){workspaceTools=!workspaceTools;styleChat();}
            if(n==5) settings(); if(n==6) repairMenu();
        });
    }
    private void settings() {
        choose("Settings",new String[]{"Sleep after "+idleMinutes+" idle minutes","Phone control","Agent access","T3 settings"},n->{
            if(n==0) new AlertDialog.Builder(this).setTitle("Idle time")
                .setSingleChoiceItems(new String[]{"2 minutes","5 minutes","10 minutes","15 minutes","30 minutes","60 minutes"},idleIndex(),(d,i)->{
                    d.dismiss(); send("settings",new String[]{"settings",String.valueOf(new int[]{2,5,10,15,30,60}[i])});
                }).show();
            if(n==1) openPackage("moe.shizuku.privileged.api"); if(n==2) ensureAccess();
            if(n==3)web.loadUrl(BASE+"settings");
        });
    }
    private int idleIndex() { int[] a={2,5,10,15,30,60}; for(int i=0;i<a.length;i++) if(a[i]==idleMinutes)return i; return 1; }
    private void repairMenu() {
        choose("Repair",new String[]{"Restart services","Repair files","Reset chat view","Termux settings","Restore Termux access"},n->{
            if(n==0) confirm("Restart services?","Running tasks will stop.","Restart",()->{
                begin(); clearChat(); stage="Restarting services"; updateUi(); send("restart",new String[]{"restart"});
            });
            if(n==1) repair();
            if(n==2) confirm("Reset chat view?","Unsent drafts and view preferences will be cleared. Saved conversations stay.","Reset",()->{
                generation++; clearChat(); getPreferences(MODE_PRIVATE).edit().remove("route").apply();
                WebStorage.getInstance().deleteAllData(); CookieManager.getInstance().removeAllCookies(done->startAgent());
            });
            if(n==3) appSettings("com.termux");
            if(n==4) confirm("Restore Termux access","Copy the setup command, paste it in Termux, then return here.","Copy & open",()->{
                String command="mkdir -p ~/.termux; printf '\\nallow-external-apps = true\\n' >> ~/.termux/termux.properties; termux-reload-settings";
                ((android.content.ClipboardManager)getSystemService(CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText("Termux access",command)); openPackage("com.termux");
            });
        });
    }
    private void showStatus() {
        statusDialog=new AlertDialog.Builder(this).setTitle("Status").setMessage(statusSummary())
            .setPositiveButton("Done",null).setNeutralButton("Phone control",(d,w)->openPackage("moe.shizuku.privileged.api")).show();
        send("diagnostics",new String[]{"diagnostics"});
    }
    private String statusSummary() { return displayStage()+"\n"+freshness()+"\n\n"+details+"Phone control: "+phoneControl; }
    private void begin() {
        generation++; desiredRunning=true; autoConnect=true; transportOkay=true; pairPending=false;
        projectPending=false;pendingProjectTitle=null;
        failure=""; phase="starting"; stage="Starting Termux"; operationSince=SystemClock.elapsedRealtime(); heartbeatAt=0;
    }
    private void startAgent() { begin(); clearChat(); updateUi(); send("start",new String[]{"start"}); }
    private void reconnect() { begin(); clearChat(); stage="Reconnecting"; updateUi(); send("start",new String[]{"start"}); }
    private void stopAgent() {
        generation++; desiredRunning=false; pairPending=false; failure=""; clearChat(); phase="stopping"; stage="Stopping tasks";
        projectPending=false;pendingProjectTitle=null;
        operationSince=SystemClock.elapsedRealtime(); updateUi(); send("stop",new String[]{"stop"});
    }
    private void fail(String text) { failure=text; autoConnect=false; chatRequested=false; updateUi(); }
    private String displayStage() {
        if(!failure.isEmpty()) return failure;
        if(projectPending)return projectStage;
        if(phase.equals("ready") && desiredRunning && !chatLoaded) return pairPending?"Pairing chat":chatRequested?"Opening chat":"Connecting chat";
        return stage;
    }
    private String freshness() {
        if(!transportOkay) return "Termux is not responding";
        if(lastReply==0) return "Waiting for Termux";
        long sinceReply=(SystemClock.elapsedRealtime()-lastReply)/1000;
        if(sinceReply>12) return "No reply for "+sinceReply+"s";
        long age=heartbeatAt>0?Math.max(0,(long)(System.currentTimeMillis()/1000d-heartbeatAt)):sinceReply;
        if(age>15 && !phase.equals("stopped")) return "Last service update "+age+"s ago";
        return "Checked "+age+"s ago";
    }
    private void updateUi() {
        if(stageText==null) return;
        boolean failed=!failure.isEmpty() || phase.equals("error"), off=phase.equals("stopped");
        boolean usable=chatLoaded && !failed && !projectPending && phase.equals("ready");
        boolean stale=!transportOkay || (lastReply>0 && SystemClock.elapsedRealtime()-lastReply>15000)
            || (heartbeatAt>0 && System.currentTimeMillis()/1000d-heartbeatAt>20 && !off);
        statusText.setText(failed?"Connection issue":stale?"Waiting for update":usable?(busy?"Working":"Connected"):off?"Sleeping":phase.equals("stopping")?"Stopping":"Connecting");
        GradientDrawable color=new GradientDrawable(); color.setShape(GradientDrawable.OVAL); color.setColor(failed||stale?AMBER:usable?GREEN:MUTED); dot.setBackground(color);
        stageText.setText(displayStage()); long seconds=(SystemClock.elapsedRealtime()-operationSince)/1000;
        elapsedText.setText(String.format(java.util.Locale.ROOT,"%d:%02d",seconds/60,seconds%60)); elapsedText.setVisibility(off||failed?View.GONE:View.VISIBLE);
        heartbeatText.setText(freshness()); heartbeatText.setVisibility(off?View.GONE:View.VISIBLE);
        progress.setVisibility(off||failed?View.GONE:View.VISIBLE); retry.setVisibility(off||failed?View.VISIBLE:View.GONE); retry.setText(off?"Start":"Retry");
        loading.setVisibility(usable?View.GONE:View.VISIBLE); web.setVisibility(usable?View.VISIBLE:View.INVISIBLE);
        if(statusDialog!=null && statusDialog.isShowing()) statusDialog.setMessage(statusSummary());
    }
    private void createWeb() {
        WebView.setWebContentsDebuggingEnabled((getApplicationInfo().flags & android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE)!=0);
        web=new WebView(this); web.setBackgroundColor(BG); WebSettings s=web.getSettings(); s.setJavaScriptEnabled(true); s.setDomStorageEnabled(true);
        s.setAllowFileAccess(false); s.setAllowContentAccess(false); s.setMediaPlaybackRequiresUserGesture(true); s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        web.setWebChromeClient(new WebChromeClient(){
            @Override public boolean onShowFileChooser(WebView v,ValueCallback<Uri[]> callback,FileChooserParams params) {
                if(fileChoice!=null) fileChoice.onReceiveValue(null); fileChoice=callback;
                try { startActivityForResult(params.createIntent(),8); } catch(Exception e) { fileChoice.onReceiveValue(null); fileChoice=null; } return true;
            }
        });
        web.setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView v,WebResourceRequest r) {
                Uri u=r.getUrl(); if("127.0.0.1".equals(u.getHost()) && u.getPort()==3773 && "http".equals(u.getScheme())) return false;
                if("https".equals(u.getScheme())||"http".equals(u.getScheme())) try{startActivity(new Intent(Intent.ACTION_VIEW,u));}catch(Exception ignored){} return true;
            }
            @Override public void onReceivedError(WebView v,WebResourceRequest r,WebResourceError e) { if(r.isForMainFrame()) {chatLoaded=false; fail("Chat could not connect");} }
            @Override public void onPageFinished(WebView v,String url) { CookieManager.getInstance().flush(); routeChanged(url); styleChat(); checkWeb(); }
            @Override public void doUpdateVisitedHistory(WebView v,String url,boolean reload) { routeChanged(url); }
            @Override public boolean onRenderProcessGone(WebView v,RenderProcessGoneDetail d) {
                content.removeView(v); v.destroy(); createWeb(); loading.bringToFront(); chatLoaded=false; fail("Chat closed unexpectedly"); return true;
            }
        }); content.addView(web,new FrameLayout.LayoutParams(-1,-1));
    }
    private void checkWeb() {
        if(!chatRequested || chatLoaded || restoring) return; int sentGeneration=generation;
        if(pendingProjectTitle!=null){
            web.evaluateJavascript("(()=>{let name="+JSONObject.quote(pendingProjectTitle)+";let b=document.querySelector('[aria-label=\"Change project\"]');if(b?.textContent.trim()===name)return true;let item=[...document.querySelectorAll('[role=menuitemradio]')].find(e=>e.textContent.trim()===name);if(item){item.click();return true}if(b&&b.getAttribute('aria-expanded')!=='true')b.click();return false})()",value->{
                if(sentGeneration==generation&&"true".equals(value))pendingProjectTitle=null;
            });return;
        }
        web.evaluateJavascript("Boolean(document.querySelector('[data-testid=\"composer-editor\"]') || document.querySelector('[data-sidebar=\"sidebar\"]'))",value->{
            if(sentGeneration==generation && "true".equals(value)) { chatLoaded=true; failure=""; updateUi(); }
        });
        if(SystemClock.elapsedRealtime()-operationSince>600000) fail("Chat did not finish loading");
    }
    private void styleChat() {
        String css="html:not(.pixel-tools) [aria-label='Open in editor'],html:not(.pixel-tools) [aria-label='Git actions'],html:not(.pixel-tools) div:has(>button[aria-label='Add action']),html:not(.pixel-tools) [aria-label='Toggle terminal drawer'],html:not(.pixel-tools) [aria-label='Toggle right panel'],html:not(.pixel-tools) .pixel-update{display:none!important}html.pixel-draft h1{display:none!important}";
        web.evaluateJavascript("(()=>{let s=document.getElementById('pixel-mobile-style');if(!s){s=document.createElement('style');s.id='pixel-mobile-style';document.head.append(s)}s.textContent="+JSONObject.quote(css)+";document.documentElement.classList.toggle('pixel-tools',"+workspaceTools+");document.documentElement.classList.toggle('pixel-draft',location.pathname.startsWith('/draft/'));})()",null);
        web.evaluateJavascript("(()=>{const trim=()=>document.querySelectorAll('[data-slot=toast-viewport] [role=dialog]').forEach(e=>{if(e.textContent.includes('Update Available:')||e.textContent.includes('provider status has not been checked'))e.classList.add('pixel-update')});trim();if(!window.pixelToastObserver){window.pixelToastObserver=new MutationObserver(trim);window.pixelToastObserver.observe(document.body,{childList:true,subtree:true})}})()",null);
    }
    private void saveRoute() {
        if(web==null||restoring) return; String url=web.getUrl();
        if(url!=null&&url.startsWith(BASE)) {
            String path=Uri.parse(url).getPath();
            if(path!=null&&(path.startsWith("/draft/")||path.matches("/[0-9a-f-]{36}/[0-9a-f-]{36}")))
                getPreferences(MODE_PRIVATE).edit().putString("route",url).apply();
        }
    }
    private void routeChanged(String url) {
        if(url==null||!url.startsWith(BASE)||url.contains("/pair")) return;
        if(restoring) { restoring=false; if(restoreRoute!=null&&!restoreRoute.equals(url)) {web.loadUrl(restoreRoute); return;} } saveRoute(); styleChat();
    }
    private void clearChat() { saveRoute(); web.stopLoading(); web.loadUrl("about:blank"); chatRequested=false; chatLoaded=false; restoring=false; }
    private void pair() { if(pairPending) return; pairPending=true; updateUi(); send("pair",new String[]{"pair"}); }
    private void ensureAccess() { if(checkSelfPermission(PERMISSION)!=PackageManager.PERMISSION_GRANTED) requestPermissions(new String[]{PERMISSION},7); else startAgent(); }
    @Override public void onRequestPermissionsResult(int code,String[] permissions,int[] grants) {
        super.onRequestPermissionsResult(code,permissions,grants); if(code==7&&grants.length>0&&grants[0]==PackageManager.PERMISSION_GRANTED) startAgent(); else {fail("Agent access is disabled"); appSettings(getPackageName());}
    }
    private void appSettings(String pkg) { startActivity(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,Uri.parse("package:"+pkg))); }
    private void openPackage(String pkg) { Intent intent=getPackageManager().getLaunchIntentForPackage(pkg); if(intent!=null) startActivity(intent); else Toast.makeText(this,"App not installed",Toast.LENGTH_SHORT).show(); }
    private void send(String action,String[] args) {
        String[] all=new String[args.length+1]; all[0]=CONTROL; System.arraycopy(args,0,all,1,args.length); dispatch(action,PREFIX+"python",all,null);
    }
    private void dispatch(String action,String path,String[] args,String stdin) {
        if(action.equals("status")&&statusPending) return;
        if(checkSelfPermission(PERMISSION)!=PackageManager.PERMISSION_GRANTED) {fail("Agent access is disabled"); return;}
        if(action.equals("status")) statusPending=true; int id=nextId++, sentGeneration=generation;
        Intent callback=new Intent(this,ResultReceiver.class).putExtra("id",id).putExtra("action",action).putExtra("generation",generation);
        PendingIntent result=PendingIntent.getBroadcast(this,id,callback,PendingIntent.FLAG_ONE_SHOT|PendingIntent.FLAG_MUTABLE); pending.put(id,result);
        Intent command=new Intent("com.termux.RUN_COMMAND").setClassName("com.termux","com.termux.app.RunCommandService")
            .putExtra("com.termux.RUN_COMMAND_PATH",path).putExtra("com.termux.RUN_COMMAND_ARGUMENTS",args)
            .putExtra("com.termux.RUN_COMMAND_WORKDIR","/data/data/com.termux/files/home").putExtra("com.termux.RUN_COMMAND_BACKGROUND",true)
            .putExtra("com.termux.RUN_COMMAND_PENDING_INTENT",result);
        if(stdin!=null) command.putExtra("com.termux.RUN_COMMAND_STDIN",stdin);
        try {startService(command);} catch(Exception e) {pending.remove(id);result.cancel();pairPending=false;statusPending=false;transportOkay=false;fail("Termux could not start");}
        handler.postDelayed(()->{
            PendingIntent waiting=pending.remove(id); if(waiting==null) return; waiting.cancel(); if(action.equals("status")) statusPending=false;
            if(sentGeneration!=generation) return; transportOkay=false; if(action.equals("pair")) pairPending=false; fail("Termux has not replied");
        },action.equals("project")?610000:action.equals("projects")?70000:action.equals("repair")?180000:action.equals("pair")?100000:(action.equals("restart")||action.equals("start"))?60000:20000);
    }
    private void result(Intent intent) {
        int id=intent.getIntExtra("id",0); if(pending.remove(id)==null)return; String action=intent.getStringExtra("action"); if(action.equals("status"))statusPending=false;
        if(intent.getIntExtra("generation",0)!=generation)return; Bundle bundle=intent.getBundleExtra("result"); if(bundle==null)return; if(action.equals("pair"))pairPending=false;
        try {
            JSONObject data=new JSONObject(bundle.getString("stdout","").trim()); transportOkay=true; lastReply=SystemClock.elapsedRealtime();
            if(action.equals("projects")||action.equals("project")){
                projectPending=false;
                if(data.has("error")){fail(data.optString("error"));return;}
                if(action.equals("projects")){
                    JSONArray repos=data.getJSONArray("repositories");String[] names=new String[repos.length()];for(int i=0;i<names.length;i++)names[i]=repos.getString(i);
                    updateUi();choose("GitHub",names,n->{projectPending=true;projectStage="Opening "+names[n];operationSince=SystemClock.elapsedRealtime();clearChat();updateUi();send("project",new String[]{"project",names[n]});});
                }else{
                    pendingProjectTitle=data.getString("project_title");chatRequested=true;chatLoaded=false;failure="";restoring=false;web.loadUrl(BASE);updateUi();
                }return;
            }
            if(action.equals("pair")&&data.has("url")&&desiredRunning) {
                String url=data.getString("url"); if(!url.startsWith(BASE+"pair#token="))throw new Exception();
                restoreRoute=getPreferences(MODE_PRIVATE).getString("route",BASE); restoring=true; chatRequested=true; web.loadUrl(url); updateUi(); return;
            }
            if(action.equals("diagnostics")) {
                StringBuilder lines=new StringBuilder(); JSONArray checks=data.optJSONArray("checks");
                if(checks!=null)for(int n=0;n<checks.length();n++){JSONObject c=checks.getJSONObject(n); lines.append(c.optString("name")).append(c.optBoolean("ok")?"  OK\n":"  Unavailable\n");}
                details=lines.toString(); String p=data.optString("phone_control","unknown"); phoneControl=p.equals("rish")||p.equals("adb")?"Connected":"Start Shizuku"; updateUi(); return;
            }
            if(action.equals("repair")&&data.optBoolean("repaired")){startAgent();return;}
            phase=data.optString("phase","error");
            if(action.equals("status")&&checkOnResume){checkOnResume=false;if(phase.equals("stopped")){startAgent();return;}}
            busy=data.optBoolean("busy"); idleMinutes=data.optInt("idle_minutes",idleMinutes); heartbeatAt=data.optDouble("updated_at",0);
            if(projectPending&&data.has("project_job")){JSONObject job=data.getJSONObject("project_job");projectStage=job.optString("stage",projectStage);heartbeatAt=job.optDouble("updated_at",heartbeatAt);}
            stage=data.optString("stage",phase.equals("starting")?"Starting T3":phase.equals("ready")?"Connected":phase.equals("stopping")?"Stopping tasks":"Sleeping");
            if(phase.equals("error")){failure=data.optString("message","Service failed");autoConnect=false;chatRequested=false;}
            if(action.equals("settings"))Toast.makeText(this,"Saved",Toast.LENGTH_SHORT).show();
            if(phase.equals("ready")&&desiredRunning&&autoConnect&&!projectPending&&!chatRequested&&!pairPending)pair();
            if(phase.equals("stopped")){chatLoaded=false;chatRequested=false;} updateUi();
            if(phase.equals("stopped")&&data.optBoolean("checkpoint_saved"))finishAndRemoveTask();
        }catch(Exception e){transportOkay=false;fail("Control files could not run. Use Repair files.");}
    }
    public static class ResultReceiver extends BroadcastReceiver {
        @Override public void onReceive(Context context,Intent intent){MainActivity app=current.get();if(app!=null)app.handler.post(()->app.result(intent));}
    }
    private final Runnable tick=new Runnable(){public void run(){
        if(!foreground)return;long now=SystemClock.elapsedRealtime();
        if(transportOkay&&(checkOnResume||!phase.equals("stopped"))&&now-lastStatusPoll>=4000){lastStatusPoll=now;send("status",interactionPending?new String[]{"status","active"}:new String[]{"status"});interactionPending=false;}
        if(now-lastWebCheck>=1000){lastWebCheck=now;checkWeb();} updateUi(); handler.postDelayed(this,1000);
    }};
    @Override public void onUserInteraction(){super.onUserInteraction();interactionPending=true;}
    @Override public void onResume(){super.onResume();foreground=true;interactionPending=true;checkOnResume=true;desiredRunning=true;transportOkay=true;if(web!=null){web.resumeTimers();web.onResume();}handler.postDelayed(tick,1000);}
    @Override public void onPause(){saveRoute();foreground=false;handler.removeCallbacks(tick);if(web!=null)web.onPause();super.onPause();}
    @Override public void onStop(){
        if(web!=null&&fileChoice==null){
            clearChat();CookieManager.getInstance().flush();web.pauseTimers();
            // Do not sit behind Termux in the task stack: closing Termux at
            // idle would otherwise resume this activity and start it again.
            if(checkSelfPermission(PERMISSION)==PackageManager.PERMISSION_GRANTED)finishAndRemoveTask();
        }
        super.onStop();
    }
    @Override public void onDestroy(){foreground=false;handler.removeCallbacksAndMessages(null);for(PendingIntent p:pending.values())p.cancel();pending.clear();if(web!=null)web.destroy();super.onDestroy();}
    @Override public void onBackPressed(){
        WebBackForwardList history=web.copyBackForwardList();int previous=history.getCurrentIndex()-1;
        String url=previous>=0?history.getItemAtIndex(previous).getUrl():"";
        if(chatLoaded&&url.startsWith(BASE)&&!url.contains("/pair"))web.goBack();else super.onBackPressed();
    }
    @Override public void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(request==8&&fileChoice!=null){fileChoice.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(result,data));fileChoice=null;}}
    private void repair(){confirm("Repair files?","Restores the app's control files. Projects and accounts stay.","Repair",()->{
        try(InputStream input=getAssets().open("runtime.zip")){
            ByteArrayOutputStream bytes=new ByteArrayOutputStream();byte[] buffer=new byte[8192];int count;while((count=input.read(buffer))!=-1)bytes.write(buffer,0,count);
            String data=android.util.Base64.encodeToString(bytes.toByteArray(),android.util.Base64.NO_WRAP);
            String script="set -eu\nexport PIXEL_APP_ID="+getPackageName()+"\nexport PATH=\"$HOME/.local/bin:$PATH\"\npython - <<'PY'\nimport base64,io,pathlib,zipfile\np=pathlib.Path.home()/'.local/share/pixel-agent/repair'\np.mkdir(parents=True,exist_ok=True)\nzipfile.ZipFile(io.BytesIO(base64.b64decode('"+data+"'))).extractall(p)\nPY\nbash \"$HOME/.local/share/pixel-agent/repair/apply-pixel-power.sh\" >/dev/null 2>&1\nprintf '{\"repaired\":true}\\n'\n";
            begin();clearChat();stage="Repairing files";updateUi();dispatch("repair",PREFIX+"bash",new String[]{"-s"},script);
        }catch(Exception e){fail("Repair files are missing. Reinstall the APK.");}
    });}
}
