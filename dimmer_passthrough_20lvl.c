#include <X11/Xlib.h>
#include <X11/extensions/shape.h>
#include <X11/Xatom.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char *argv[]) {
    Display *d = XOpenDisplay(NULL);
    if (!d) return 1;
    
    int s = DefaultScreen(d);
    Window root = RootWindow(d, s);
    
    XSetWindowAttributes attrs;
    attrs.override_redirect = True;
    attrs.background_pixel = BlackPixel(d, s);
    attrs.colormap = DefaultColormap(d, s);
    
    Window w = XCreateWindow(
        d, root,
        0, 0,
        DisplayWidth(d, s), DisplayHeight(d, s),
        0,
        CopyFromParent,
        InputOutput,
        CopyFromParent,
        CWOverrideRedirect | CWBackPixel,
        &attrs
    );
    
    Atom window_type = XInternAtom(d, "_NET_WM_WINDOW_TYPE", False);
    Atom desktop_type = XInternAtom(d, "_NET_WM_WINDOW_TYPE_DESKTOP", False);
    XChangeProperty(d, w, window_type, XA_ATOM, 32, PropModeReplace, (unsigned char*)&desktop_type, 1);
    
    // 20 levels: 1=5% dark (brightest) to 20=100% dark (black)
    int level = 10; // Default 50%
    if (argc > 1) level = atoi(argv[1]);
    if (level < 1) level = 1;
    if (level > 20) level = 20;
    
    // Convert level to opacity (level 20 = 0xFF000000 = fully opaque black)
    // Use unsigned long long to avoid integer overflow
    unsigned long opacity = (unsigned long long)level * 0xFF000000ULL / 20ULL;
    
    Atom opacity_atom = XInternAtom(d, "_NET_WM_WINDOW_OPACITY", False);
    XChangeProperty(d, w, opacity_atom, XA_CARDINAL, 32, PropModeReplace, (unsigned char*)&opacity, 1);
    
    int event_base, error_base;
    if (XShapeQueryExtension(d, &event_base, &error_base)) {
        Region region = XCreateRegion();
        XShapeCombineRegion(d, w, ShapeInput, 0, 0, region, ShapeSet);
        XDestroyRegion(region);
    }
    
    XMapWindow(d, w);
    XFlush(d);
    XSync(d, False);
    
    sleep(3600);
    
    XDestroyWindow(d, w);
    XCloseDisplay(d);
    return 0;
}
