#ifndef HOME_SENSOR_H
#define HOME_SENSOR_H

namespace HomeSensor {
  // Initialize any necessary pins for the sensor.
  void begin();

  // Returns true when the sensor detects home.
  bool homeActive();

  // Only returns true the first time this is called after the rising edge is
  // detected. Returns false until the next rising edge. A rising edge only
  // counts once the contact has been open for the debounce time, so a bounce
  // as the contact opens or closes isn't taken for another edge.
  bool detectRisingEdge();
}

#endif
