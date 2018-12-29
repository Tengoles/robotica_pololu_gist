#include <PololuQTRSensors.h>
#include <OrangutanLCD.h>
#include <OrangutanPushbuttons.h>
#include <OrangutanLEDs.h>
#include <OrangutanMotors.h>
#include <OrangutanBuzzer.h>
#include <OrangutanAnalog.h>
#include <Pololu3pi.h>

#define bSize 4

Pololu3pi robot;

char cntChar; // Variable para recibir cantidad de datos del puerto serie
char Buffer[bSize]; //array donde guardo los comandos

char prueba;

int ledpin = 7; // Pin donde se encuentra conectado el led (pin 7)

int velocIzq = 0;
int velocDer = 0;

char stateIzq = 0;
char stateDer = 0;

void setup() {
  // se hace al principio para que todo funque
  robot.init(2000);

  // Comunicación serie a 9600 baudios
  Serial.begin(9600);
  Serial.flush();

  // Pin 7 como salida
  pinMode(ledpin, OUTPUT);

  // Muestro la bateria y espero a que toquen B para arrancar
  while (!OrangutanPushbuttons::isPressed(BUTTON_B))
  {
    int bat = OrangutanAnalog::readBatteryMillivolts();

    OrangutanLCD::clear();
    OrangutanLCD::print(bat);
    OrangutanLCD::print("mV");
    OrangutanLCD::gotoXY(0, 1);

    delay(100);
  }

  OrangutanLCD::clear();
  OrangutanLCD::print("BTKR");
  OrangutanLCD::gotoXY(0, 1);

  // espero que suelten el boton antes de arrancar
  OrangutanPushbuttons::waitForRelease(BUTTON_B);
  delay(1000);//espero un cacho para que saques el dedo

  //mando comando de que estoy disponible

}

void loop() {
  // Si hay datos disponibles en el buffer
  if (Serial.available() >= bSize)
  {
    // Leer un byte y colocarlo en variable
    cntChar = Serial.readBytesUntil('\n', Buffer, bSize);
    Serial.write(Buffer);
    // Procesar comando
    //sentido rueda izquierda
    if ((Buffer[0] & 0xF0) == 0x50)//me quedo con los primeros 4 bits y defino el sentido
    {
      stateIzq = 1;
    }
    else if ((Buffer[0] & 0xF0) == 0xA0) //me quedo con los primeros 4 bits y defino el sentido
    {
      stateIzq = -1;
    }
    else //si tengo cualquier otra cosa, freno
    {
      stateIzq = 0;
    }

    //sentido rueda derecha
    if ((Buffer[0] & 0x0F) == 0x05)//me quedo con los ultimos 4 bits y defino el sentido
    {
      stateDer = 1;
    }
    else if ((Buffer[0] & 0x0F) == 0x0A) //me quedo con los ultimos 4 bits y defino el sentido
    {
      stateDer = -1;
    }
    else //si tengo cualquier otra cosa, freno
    {
      stateDer = 0;
    }

    //Ahora seteo la velocidad de las ruedas
    velocIzq = stateIzq * Buffer[1];
    velocDer = stateDer * Buffer[2];

    //seteo efectivamente la velocidad de las ruedas
    OrangutanMotors::setSpeeds(velocIzq, velocDer);
    Serial.flush();
    for (int i = 0; i < bSize; i++)
    {
      Buffer[i] = 0;
    }
  }
  // Podemos hacer otras cosas aquí
  delay(10);
}
