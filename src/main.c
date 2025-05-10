#include <uxhw.h>
#include <math.h>
#include <stdlib.h>
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
	kCalculateNoCommand		= 0, /* Go to idle */
	kCalculateWindow     = 1, /* Calculate window */
} SignaloidSoCCommand;

static float getWeightedMean(float * values, size_t count)
{
  float dist = UxHwFloatDistFromSamples(values, count);
  float variance = UxHwFloatNthMoment(dist, 2);
  float mean = UxHwFloatNthMoment(dist, 1);

  WeightedFloatSample *weightedSamples = (WeightedFloatSample *)checkedCalloc(count, sizeof(WeightedFloatSample), __FILE__, __LINE__);

  for (size_t i = 0; i < count; i++) {
    float weight = 1.0f;
    if (variance > 0.0f) {
      float diff = values[i] - mean;
      weight = expf(-(diff * diff) / (2.0f * variance));
    }

    weightedSamples[i] = {.sample = values[i], .sampleWeight = weight};
  }

  float weightedMean = UxHwFloatDistFromWeightedSamples(weightedSamples, count);

  free(weightedSamples);

  return weightedMean;
}

int
main(void)
{
	volatile SignaloidSoCStatus *	mmioStatus		= (SignaloidSoCStatus *) kSignaloidSoCDeviceConstantsStatusAddress;
	volatile uint32_t *		mmioSoCControl		= (uint32_t *) kSignaloidSoCDeviceConstantsSoCControlAddress;
	volatile SignaloidSoCCommand *	mmioCommand		= (SignaloidSoCCommand *) kSignaloidSoCDeviceConstantsCommandAddress;

	volatile double *		MOSIBuffer		= (double *) kSignaloidSoCDeviceConstantsMOSIBufferAddress;
	volatile uint32_t *		MOSIBufferUInt		= (uint32_t *) kSignaloidSoCDeviceConstantsMOSIBufferAddress;

	volatile double *		MISOBuffer		= (double *) kSignaloidSoCDeviceConstantsMISOBufferAddress;
	volatile uint32_t *		resultBufferSize	= (uint32_t *) kSignaloidSoCDeviceConstantsMISOBufferAddress;
	volatile uint8_t *		resultBuffer		= (uint8_t *) (kSignaloidSoCDeviceConstantsMISOBufferAddress + sizeof(uint32_t));

	while (1)
	{
		/*
		 *	Set status to "waitingForCommand"
		 */
		*mmioStatus = kSignaloidSoCStatusWaitingForCommand;

		/*
		 *	Block until command is issued
		 */
		while (*mmioCommand == kCalculateNoCommand) {}

		/*
		 *	Set status to inform host that calculation will start
		 */
		*mmioStatus = kSignaloidSoCStatusCalculating;

		/*
		 *	Turn on status LED
		 */
		*mmioSoCControl = 0xffffffff;
    uint32_t resultSize = sizeof(float);

		switch (*mmioCommand)
		{	
			/*
			 *	All of the following commands parse the inputs in the same way
			 */
			case kCalculateWindow:

        // First argument is the number of samples in the distribution
        uint16_t numSamples = MOSIBufferUInt[0];

				/*
				 *	Calculate
				 */
				switch (*mmioCommand)
				{
          case kCalculateWindow:
            /*
             *	Calculate window's weighted mean natively
             */
            float result = getWeightedMean((MOSIBuffer + sizeof(uint32_t)), numSamples);
            // Copy the result to the MISO buffer
            MISOBuffer[0] = result;
            break;
					default:
						break;
				}

				// TODO: Does this function even exist?
				// resultSize = UxHwFloatDistributionToByteArray(result, resultBuffer, kSignaloidSoCCommonConstantsMISOBufferSizeBytes - sizeof(uint32_t));
				*resultBufferSize = resultSize;

				/*
				 *	Set status
				 */
				*mmioStatus = kSignaloidSoCStatusDone;
				break;

			default:
				*mmioStatus = kSignaloidSoCStatusInvalidCommand;
				break;
		}

		/*
		 *	Turn off status LED
		 */
		*mmioSoCControl = 0x00000000;

		/*
		 *	Block until command is cleared
		 */
		while (*mmioCommand != kCalculateNoCommand) {}
	}
}
