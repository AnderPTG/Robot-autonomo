/*
  Indicador LED de estado para robot autónomo (BFS)
  Hardware: Arduino UNO Q (Arduino App Lab)

  Conexiones (3 pines):
    - PIN_DETENCION -> LED de detención completa (en paradas y punto final)
    - PIN_MOVIMIENTO -> LED de movimiento en línea recta
    - PIN_GIRO       -> LED de giro (cambio de dirección)

  Comunicación:
    - El sketch registra la función "recibir_ruta" con Bridge.provide().
    - El lado Python (bfs_ruta.py) calcula la ruta BFS y llama a
      "recibir_ruta" mediante Bridge.call(), enviando el estado
      ("OK"/"ERROR") y la ruta como string "f0,c0;f1,c1;...".
    - El sketch registra además "actualizar_estado_motor" con Bridge.provide().
      Python llama a esta función con uno de los estados:
        "MOVIMIENTO" -> LED en PIN_MOVIMIENTO (pin 9)
        "GIRO"       -> LED en PIN_GIRO (pin 10)
        "DETENCION"  -> LED en PIN_DETENCION (pin 8)
*/

#include <Arduino_RouterBridge.h>

const int PIN_DETENCION  = 5;
const int PIN_MOVIMIENTO = 3;
const int PIN_GIRO       = 4;

const int PIN_SENSOR_CHOQUE = 2; // entrada digital: HIGH = colisión detectada

void apagarLeds() {
  digitalWrite(PIN_DETENCION, LOW);
  digitalWrite(PIN_MOVIMIENTO, LOW);
  digitalWrite(PIN_GIRO, LOW);
}

void imprimirPuntos(String puntos) {
  int inicio = 0;
  while (inicio < (int)puntos.length()) {
    int fin = puntos.indexOf(';', inicio);
    if (fin == -1) fin = puntos.length();

    String par = puntos.substring(inicio, fin);
    int coma = par.indexOf(',');
    if (coma != -1) {
      Monitor.print("(");
      Monitor.print(par.substring(0, coma));   // fila
      Monitor.print(", ");
      Monitor.print(par.substring(coma + 1));  // columna
      Monitor.println(")");
    }

    inicio = fin + 1;
  }
}

// Callback RPC invocado desde Python cuando termina el BFS
String recibir_ruta(String estado, String puntos) {
  if (estado == "ERROR") {
    digitalWrite(PIN_MOVIMIENTO, LOW);
    digitalWrite(PIN_DETENCION, HIGH);
    Monitor.println("No se encontro ruta posible.");
    return "FAIL";
  }

  digitalWrite(PIN_MOVIMIENTO, HIGH);
  Monitor.println("Ruta generada con exito:");
  imprimirPuntos(puntos);

  return "ACK";
}

// Callback RPC invocado desde Python para reportar el estado del motor
String actualizar_estado_motor(String estado) {
  apagarLeds();

  if (estado == "MOVIMIENTO") {
    digitalWrite(PIN_MOVIMIENTO, HIGH);
    Monitor.println("Robot en movimiento.");
  } else if (estado == "GIRO") {
    digitalWrite(PIN_GIRO, HIGH);
    Monitor.println("Giro realizado.");
  } else if (estado == "DETENCION") {
    digitalWrite(PIN_DETENCION, HIGH);
    Monitor.println("Detencion completa (parada o punto final).");
  } else {
    Monitor.println("Estado de motor desconocido: " + estado);
    return "FAIL";
  }

  return "ACK";
}

void setup() {
  pinMode(PIN_DETENCION, OUTPUT);
  pinMode(PIN_MOVIMIENTO, OUTPUT);
  pinMode(PIN_GIRO, OUTPUT);
  pinMode(PIN_SENSOR_CHOQUE, INPUT);

  apagarLeds();

  Monitor.begin(115200);
  Bridge.begin();

  // Estado inicial: esperando ruta -> LED de detención encendido
  digitalWrite(PIN_DETENCION, HIGH);
  Monitor.println("Esperando ruta BFS...");

  // Registra las funciones que Python invocará
  Bridge.provide("recibir_ruta", recibir_ruta);
  Bridge.provide("actualizar_estado_motor", actualizar_estado_motor);
}

void loop() {
  if (digitalRead(PIN_SENSOR_CHOQUE) == HIGH) {
    indicarColision();
  }
}

void indicarColision() {
  apagarLeds();
  digitalWrite(PIN_DETENCION, HIGH);
  Monitor.println("Colision detectada con el obstaculo!");
}