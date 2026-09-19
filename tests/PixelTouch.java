import android.os.SystemClock;
import android.view.InputDevice;
import android.view.InputEvent;
import android.view.MotionEvent;
import java.lang.reflect.Method;

/** ADB-shell-only touch test driver. No app install, service, or extra permission. */
public final class PixelTouch {
    static Object manager;
    static Method inject;
    static long down;
    static void event(int action, float[][] points) throws Exception {
        MotionEvent.PointerProperties[] props = new MotionEvent.PointerProperties[points.length];
        MotionEvent.PointerCoords[] coords = new MotionEvent.PointerCoords[points.length];
        for (int i = 0; i < points.length; i++) {
            props[i] = new MotionEvent.PointerProperties();
            props[i].id = i;
            props[i].toolType = MotionEvent.TOOL_TYPE_FINGER;
            coords[i] = new MotionEvent.PointerCoords();
            coords[i].x = points[i][0]; coords[i].y = points[i][1];
            coords[i].pressure = 1; coords[i].size = 0.1f;
        }
        MotionEvent e = MotionEvent.obtain(down, SystemClock.uptimeMillis(), action,
            points.length, props, coords, 0, 0, 1, 1, 0, 0, InputDevice.SOURCE_TOUCHSCREEN, 0);
        try {
            if (!Boolean.TRUE.equals(inject.invoke(manager, e, 2))) throw new Exception("Injection failed");
        } finally { e.recycle(); }
    }
    public static void main(String[] args) throws Exception {
        Class<?> cls = Class.forName("android.hardware.input.InputManagerGlobal");
        manager = cls.getMethod("getInstance").invoke(null);
        inject = cls.getMethod("injectInputEvent", InputEvent.class, int.class);
        // gesture fingerCount x y dx dy durationMs [holdX holdY]
        int count = Integer.parseInt(args[0]);
        float x = Float.parseFloat(args[1]), y = Float.parseFloat(args[2]);
        float dx = Float.parseFloat(args[3]), dy = Float.parseFloat(args[4]);
        int ms = Integer.parseInt(args[5]);
        boolean helper = args.length == 8;
        float hx = helper ? Float.parseFloat(args[6]) : 0;
        float hy = helper ? Float.parseFloat(args[7]) : 0;
        int total = count + (helper ? 1 : 0);
        down = SystemClock.uptimeMillis();
        float[][] points = new float[total][2];
        for (int i = 0; i < total; i++) {
            points[i][0] = helper && i == 0 ? hx : x + (i - (helper ? 1 : 0)) * 100;
            points[i][1] = helper && i == 0 ? hy : y;
            float[][] subset = java.util.Arrays.copyOf(points, i + 1);
            event(i == 0 ? MotionEvent.ACTION_DOWN : MotionEvent.ACTION_POINTER_DOWN | (i << 8), subset);
            SystemClock.sleep(40);
        }
        int steps = Math.max(1, ms / 16);
        for (int step = 1; step <= steps; step++) {
            for (int i = helper ? 1 : 0; i < total; i++) {
                points[i][0] = x + (i - (helper ? 1 : 0)) * 100 + dx * step / steps;
                points[i][1] = y + dy * step / steps;
            }
            if (dx != 0 || dy != 0) event(MotionEvent.ACTION_MOVE, points);
            SystemClock.sleep(ms / steps);
        }
        for (int i = total - 1; i >= 0; i--) {
            event(i == 0 ? MotionEvent.ACTION_UP : MotionEvent.ACTION_POINTER_UP | (i << 8),
                java.util.Arrays.copyOf(points, i + 1));
            SystemClock.sleep(40);
        }
        System.out.println("Injected " + count + "-finger gesture" + (helper ? " with held side button" : ""));
    }
}
