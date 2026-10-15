// Decode the "encoded polyline" format used by OTP for legGeometry.points
// (Google's algorithm, 5 decimals). Returns [longitude, latitude] pairs, the
// order used by GeoJSON and MapLibre.

export function decodePolyline(encoded, precision = 5) {
  const factor = 10 ** precision;
  const coordinates = [];
  let index = 0;
  let lat = 0;
  let lon = 0;
  const next = () => {
    let result = 0;
    let shift = 0;
    let byte;
    do {
      if (index >= encoded.length) throw new Error('truncated polyline');
      byte = encoded.charCodeAt(index++) - 63;
      result |= (byte & 0x1f) << shift;
      shift += 5;
    } while (byte >= 0x20);
    return result & 1 ? ~(result >> 1) : result >> 1;
  };
  while (index < (encoded || '').length) {
    lat += next();
    lon += next();
    coordinates.push([lon / factor, lat / factor]);
  }
  return coordinates;
}

/** Encode [longitude, latitude] pairs (used by the test fixtures). */
export function encodePolyline(coordinates, precision = 5) {
  const factor = 10 ** precision;
  let out = '';
  let prevLat = 0;
  let prevLon = 0;
  const put = (value) => {
    let v = value < 0 ? ~(value << 1) : value << 1;
    while (v >= 0x20) {
      out += String.fromCharCode((0x20 | (v & 0x1f)) + 63);
      v >>= 5;
    }
    out += String.fromCharCode(v + 63);
  };
  for (const [lon, lat] of coordinates) {
    const la = Math.round(lat * factor);
    const lo = Math.round(lon * factor);
    put(la - prevLat);
    put(lo - prevLon);
    prevLat = la;
    prevLon = lo;
  }
  return out;
}
