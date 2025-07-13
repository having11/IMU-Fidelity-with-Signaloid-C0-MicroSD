#include <uxhw.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>
#include "C0microSDConstants.h"

/**
 * Input data in the buffer:
 * 0 - uint32_t -> number of samples
 * 4 - float * -> start of sample 0 to sample N
 *
 * Output data in the buffer:
 * 0 - float -> weighted mean of samples
 */

typedef enum
{
  kCalculateNoCommand = 0, /* Go to idle */
  kCalculateWindow = 1,    /* Calculate window */
} SignaloidSoCCommand;

static float getWeightedMean(float *values, size_t count)
{
  float dist = UxHwFloatDistFromSamples(values, count);
  float variance = UxHwFloatNthMoment(dist, 2);
  float mean = UxHwFloatNthMoment(dist, 1);

  WeightedFloatSample *weightedSamples = (WeightedFloatSample *)malloc(count * sizeof(WeightedFloatSample));

  for (size_t i = 0; i < count; i++)
  {
    float weight = 1.0f;
    if (variance > 0.0f)
    {
      float diff = values[i] - mean;
      weight = expf(-(diff * diff) / (2.0f * variance));
    }

    weightedSamples[i] = (WeightedFloatSample){.sample = values[i], .sampleWeight = weight};
  }

  float weightedMean = UxHwFloatDistFromWeightedSamples(weightedSamples, count);

  free(weightedSamples);

  return weightedMean;
}

int main(void)
{
  volatile SignaloidSoCStatus *mmioStatus = (SignaloidSoCStatus *)kSignaloidSoCDeviceConstantsStatusAddress;
  volatile uint32_t *mmioSoCControl = (uint32_t *)kSignaloidSoCDeviceConstantsSoCControlAddress;
  volatile SignaloidSoCCommand *mmioCommand = (SignaloidSoCCommand *)kSignaloidSoCDeviceConstantsCommandAddress;

  volatile float *MOSIBuffer = (float *)kSignaloidSoCDeviceConstantsMOSIBufferAddress;
  volatile uint32_t *MOSIBufferUInt = (uint32_t *)kSignaloidSoCDeviceConstantsMOSIBufferAddress;

  volatile float *MISOBuffer = (float *)kSignaloidSoCDeviceConstantsMISOBufferAddress;
  volatile uint32_t *resultBufferSize = (uint32_t *)kSignaloidSoCDeviceConstantsMISOBufferAddress;
  volatile uint8_t *resultBuffer = (uint8_t *)(kSignaloidSoCDeviceConstantsMISOBufferAddress + sizeof(uint32_t));

  while (1)
  {
    /*
     *	Set status to "waitingForCommand"
     */
    *mmioStatus = kSignaloidSoCStatusWaitingForCommand;

    /*
     *	Block until command is issued
     */
    while (*mmioCommand == kCalculateNoCommand)
    {
    }

    /*
     *	Set status to inform host that calculation will start
     */
    *mmioStatus = kSignaloidSoCStatusCalculating;

    /*
     *	Turn on status LED
     */
    float result;

    switch (*mmioCommand)
    {
    /*
     *	All of the following commands parse the inputs in the same way
     */
    case kCalculateWindow:
    {
      // First argument is the number of samples in the distribution
      uint32_t numSamples = (uint32_t)MOSIBuffer[0];

      /*
       *	Calculate
       */
      /*
       *	Calculate window's weighted mean natively
       */
      *mmioSoCControl = 0xffffffff;
      result = getWeightedMean((float *)((uint8_t *)MOSIBuffer + sizeof(float)), numSamples);
      // Copy the result to the MISO buffer
      memcpy(resultBuffer, &result, sizeof(float));

      // resultSize = UxHwFloatDistributionToByteArray(result, resultBuffer, kSignaloidSoCCommonConstantsMISOBufferSizeBytes - sizeof(uint32_t));
      *resultBufferSize = sizeof(float);

      /*
       *	Turn off status LED
       */
      *mmioSoCControl = 0x00000000;

      /*
       *	Set status
       */
      *mmioStatus = kSignaloidSoCStatusDone;
    }
    break;

    default:
      *mmioStatus = kSignaloidSoCStatusInvalidCommand;
      break;
    }

    /*
     *	Block until command is cleared
     */
    while (*mmioCommand != kCalculateNoCommand)
    {
    }
  }
}
