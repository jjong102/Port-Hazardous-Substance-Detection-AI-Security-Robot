import 'dart:math' as math;

double deg2rad(double d) => d * math.pi / 180.0;
double rad2deg(double r) => r * 180.0 / math.pi;
double wrapDeg180(double d) => (d + 540.0) % 360.0 - 180.0;   // [-180,180)
double wrapDeg360(double d) => (d % 360.0 + 360.0) % 360.0;   // [0,360)

double bearingDegrees(double lat1, double lon1, double lat2, double lon2) {
  const eps = 1e-12;
  if (!(lat1.isFinite && lon1.isFinite && lat2.isFinite && lon2.isFinite)) return double.nan;
  if ((lat1 - lat2).abs() < eps && (lon1 - lon2).abs() < eps) return 0.0;

  final phi1 = deg2rad(lat1);
  final phi2 = deg2rad(lat2);
  final dLam = deg2rad(wrapDeg180(lon2 - lon1));

  final y = math.sin(dLam) * math.cos(phi2);
  final x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dLam);
  final th = math.atan2(y, x);
  return wrapDeg360(rad2deg(th));
}
