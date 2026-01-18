This application will capture and visualize humidity and temperature data gathered by sensors using the SmartThings framework documented at https://developer.smartthings.com/docs/api/public.  Let me know if you need any help accessing this documentation.

You will plan the design for a minimal application to provide this functionality.  Key requirements of the initial version are:
* Connect to SmartThings,
* Pull the latest humidity and temperature data from two devices,
* Append new data to a CSV tracking historic data pulls, and
* Create a basic time series plot of the data.
Note that the data itself is logged by SmartThings using time of change and new value, rather than a datapoint for each point in time.

You are free to evaluate the tool chain you'd like to use.  Stack should either by Python or TypeScript based.  Can be either desktop or web.  You must first present your motivation for using either Python or TypeScript and get my approval, then present your proposed stack within that language along with an alternative stack and talk through the trade offs.  I will then approve one stack or another.

Once we pin down specifics then I will instruct you to assemble the application.  The application will be a minimal project that should be easy to get running in a single session.