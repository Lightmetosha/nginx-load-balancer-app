from pathlib import Path
import sys

root = Path(sys.argv[1])
main = root / 'app/src/main/java/com/lightme/fittrack/MainActivity.kt'
theme = root / 'app/src/main/java/com/lightme/fittrack/ui/theme/Theme.kt'

s = main.read_text()
s = s.replace('import androidx.health.connect.client.permission.PermissionController', 'import androidx.health.connect.client.PermissionController')
s = s.replace('import com.google.android.gms.mlkit.barcode.GmsBarcodeScanning', 'import com.google.mlkit.vision.codescanner.GmsBarcodeScanning')
s = s.replace('import com.google.android.gms.mlkit.barcode.GmsBarcodeScannerOptions', 'import com.google.mlkit.vision.codescanner.GmsBarcodeScannerOptions')
old = '@Composable fun WeightChart(data:List<WeightEntry>,modifier:Modifier){Canvas(modifier){if(data.size<2)return@Canvas;val vals=data.map{it.kg};val lo=vals.min();val hi=vals.max();val range=max(hi-lo,1.0);val dx=size.width/(data.size-1);for(i in 0 until data.size-1){fun y(v:Double)=size.height-(((v-lo)/range)*size.height*.8+size.height*.1).toFloat();drawLine(Color(0xFF8B6CFF),Offset(i*dx,y(vals[i])),Offset((i+1)*dx,y(vals[i+1])),5f)}}}'
new = '''@Composable
fun WeightChart(data: List<WeightEntry>, modifier: Modifier) {
    Canvas(modifier) {
        if (data.size < 2) return@Canvas
        val vals = data.map { it.kg }
        val lo = vals.minOrNull() ?: return@Canvas
        val hi = vals.maxOrNull() ?: return@Canvas
        val range = max(hi - lo, 1.0)
        val dx = size.width / (data.size - 1)
        fun chartY(value: Double): Float =
            size.height - ((((value - lo) / range) * size.height * 0.8) + size.height * 0.1).toFloat()
        for (i in 0 until data.size - 1) {
            drawLine(
                color = Color(0xFF8B6CFF),
                start = Offset(i * dx, chartY(vals[i])),
                end = Offset((i + 1) * dx, chartY(vals[i + 1])),
                strokeWidth = 5f
            )
        }
    }
}'''
if old in s:
    s = s.replace(old, new)
if '@OptIn(ExperimentalMaterial3Api::class)\n@Composable fun ActiveWorkoutScreen' not in s:
    s = s.replace('@Composable fun ActiveWorkoutScreen(', '@OptIn(ExperimentalMaterial3Api::class)\n@Composable fun ActiveWorkoutScreen(')
main.write_text(s)

t = theme.read_text()
t = t.replace('@Composable fun FitTheme(content:@Composable()->Unit){ MaterialTheme(colorScheme=Dark, typography=Typography(), content=content) }', '''@Composable
fun FitTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = Dark,
        typography = Typography(),
        content = content
    )
}''')
theme.write_text(t)
