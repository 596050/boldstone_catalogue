import logging
import sys

def setup_logging():
    # Root logger configuration
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s %(levelname)s - %(message)s",
        stream=sys.stdout
    )

    # suppress ib_insync warnings to FILE WRITING ONLY
    logging.getLogger('ib_insync').setLevel(logging.WARNING)
    logging.getLogger('ib_insync').propagate = False
    
    
    # Keep your own module logging at INFO or DEBUG as desired
    logging.getLogger('order_management').setLevel(logging.INFO)
    # if the error says 'Error 201, reqId', suppress it
    logging.getLogger('order_management').setLevel(logging.WARNING)
    logging.getLogger('order_management').propagate = False
    logging.getLogger('MarketMaker').setLevel(logging.INFO)