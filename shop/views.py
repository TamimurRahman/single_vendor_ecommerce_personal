from django.shortcuts import render,redirect,get_object_or_404
from django.contrib.auth import login,authenticate,logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.db.models import Min, Max, Avg, Q
from . import models
from .forms import RegistrationForm, RatingForms, CheckoutForm
from django.contrib.auth.decorators import login_required
from .utils import generate_sslcommerz_payment, send_order_confirmation_email
from django.views.decorators.csrf import csrf_exempt
# Create your views here.

def home(request):
    featured_products = models.Product.objects.filter(available=True).order_by('-created')[:8]
    categories = models.Category.objects.all()
    context = {
        'featured_products':featured_products,
        'categories':categories,
    }
    return render(request,'home.html',context)

def product_list(request,category_slug=None):
    category = None
    categories = models.Category.objects.all()
    products = models.Product.objects.filter(available=True)

    if category_slug:
        category = get_object_or_404(models.Category,slug=category_slug)
        products = products.filter(category=category)
    
    min_price = products.aggregate(Min('price'))['price__min']
    max_price = products.aggregate(Max('price'))['price__max']

    if request.GET.get('min_price'):
        products = products.filter(price__gte=request.GET.get('min_price'))
    if request.GET.get('max_price'):
        products = products.filter(price__lte=request.GET.get('max_price'))
    if request.GET.get('rating'):
        min_rating = request.GET.get('rating')
        products = products.annotate(avg_rating=Avg('ratings__rating')).filter(avg_rating__gte=min_rating) #aitar kaj holo suppose user 4 rating er product dekhte chasse so aita return korbe (>=4) er rating

    if request.GET.get('search'):
        query = request.GET.get('search')
        products = products.filter(
            Q(name__icontains = query)|
            Q(description__icontains = query)|
            Q(category__name__icontains = query)
        )
    
    context = {
        'category':category,
        'categories':categories,
        'products':products,
        'min_price':min_price,
        'max_price':max_price,
    }

    return render(request,'shop/product_list.html',context)

def product_detail(request,slug):
    product = get_object_or_404(models.Product,slug=slug,available=True)
    related_products = models.Product.objects.filter(category=product.category).exclude(id=product.id)
    user_rating = None
    if request.user.is_authenticate:
        try:
            user_rating = models.Rating.objects.get(product=product,user=request.user)
        except models.Rating.DoesNotExist:
            pass
    rating_form = RatingForms(instance=user_rating)
    context = {
        'product':product,
        'related_products':related_products,
        'user_rating':user_rating,
        'rating_form':rating_form,
    }
    return render(request,'shop/product_detail.html',context)

@login_required
def cart_detail(request):
    try:
        cart = models.Cart.objects.get(user=request.user)
    except models.Cart.DoesNotExist:
        cart = models.Cart.objects.create(user=request.user)
    
    return render(request,'shop/cart.html',{'cart':cart})
@login_required
def cart_add(request,product_id):
    product = get_object_or_404(models.Product,id=product_id)
    try:
        cart = models.Cart.objects.get(user=request.user)
    except:
        cart  = models.Cart.objects.create(user=request.user)
    
    try:
        cart_item = models.CartItem.objects.get(cart=cart,product=product)
        cart_item.quantity +=1
        cart_item.save()
    except models.CartItem.DoesNotExist:
        models.CartItem.objects.create(cart=cart,product=product,quantity=1)
    
    messages.success(request,f'{product.name} has been added to your cart!')
    return redirect('product_detail',slug=product.slug)


@login_required
def cart_remove(request,product_id):
    cart = get_object_or_404(models.Cart,user=request.user)
    product = get_object_or_404(models.Product,id=product_id)
    cart_item = get_object_or_404(models.CartItem,cart=cart,product=product)
    cart_item.delete()
    messages.success(request, f'{product.name} has been removed from your cart!')
    return redirect('cart_detail')


@login_required
def cart_update(request,product_id):
    cart = get_object_or_404(models.Cart,user=request.user)
    product = get_object_or_404(models.Product,id=product_id)
    cart_item = get_object_or_404(models.CartItem,cart=cart,product=product)
    quantity = int(request.POST.get('quantity',1))

    if quantity <=0:
        cart_item.delete()
        messages.success(request,f'{product.name} has been removed from your cart!')
    else:
        cart_item.quantity = quantity
        cart.save()
        messages.success(request,f'cart updated successfully!')
    return  redirect('cart_detail')

@login_required
def checkout(request):
    try:
        cart = models.Cart.objects.get(user=request.user)
        if not cart.items.exists():
            messages.warning(request,'your cart is empty!')
            return redirect('')
    except models.Cart.DoesNotExist:
        messages.warning(request,'Your cart is empty!')
        return redirect('cart_detail')
    
    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.save()

            for item in cart.items.all():
                models.OrderItem.objects.create(
                    order = order,
                    product=item.product,
                    price = item.product.price,
                    quantity = item.quantity,
                )
            cart.items.all().delete()
            request.session['order_id'] = order.id
            return redirect('payment_process')
    else:
        initial_data={}
        if request.user.first_name:
            initial_data['first_name']=request.user.first_name
        if request.user.last_name:
            initial_data['last_name']=request.user.last_name
        if request.user.email:
            initial_data['email'] = request.user.email
        
        form = CheckoutForm(initial=initial_data)
        return render(request,'shop/checkout.html',{'cart':cart,'form':form})

@csrf_exempt
@login_required
def payment_process(request):
    order_id = request.session.get('order_id')
    if not order_id:
        return redirect('home')
    order = get_object_or_404(models.Order,id=order_id)
    payment_data = generate_sslcommerz_payment(order,request)

    if payment_data['status']=='SUCCESS':
        return redirect(payment_data['GatewayPageURL'])
    else:
        messages.error(request,'Payment gateway error. Please Try again.')
        return redirect('checkout')

@csrf_exempt
@login_required
def payment_success(request,order_id):
    order = get_object_or_404(models.Order,id=order_id,user=request.user)
    order.paid = True
    order.status = 'processing'
    order.transaction_id = order.id
    order.save()

    order_items = order.items.all()
    for item in order_items:
        product = item.product
        product.stock -= item.quantity

        if product.stock <0:
            product.stock = 0
        product.save()
    send_order_confirmation_email(order)
    messages.success(request,'Payment successful')
    return redirect('profile')

@csrf_exempt
@login_required
def payment_fail(request,order_id):
    order = get_object_or_404(models.Order,id=order_id,user=request.user)
    order.status = 'canceled'
    order.save()
    return redirect('checkout')

@csrf_exempt
@login_required
def payment_cancel(request,order_id):
    order = get_object_or_404(models.Order,id=order_id,user=request.user)
    order.status = 'canceled'
    order.save()
    return redirect('cart_detail')


@login_required
def profile(request):
    tab = request.GET.get('tab')
    orders = models.Order.objects.filter(user=request.user).order_by('-created')
    completed_orders = orders.filter(status='delivered').count()
    total_spent = sum(order.get_tottal_cost for order in orders if order.paid)
    order_history_active=(tab=='orders')
    context={
        'user':request.user,
        'orders':orders,
        'order history active':order_history_active,
        'completed_orders':completed_orders,
        'total_spent':total_spent
    }
    return render(request,'shop/profile.html',)

@login_required
def rate_product(request,product_id):
    product = get_object_or_404(models.Product,id=product_id)
    ordered_items = models.OrderItem.objects.filter(
        order__user = request.user,
        order__paid =True,
        product=product,
    )
    if not ordered_items.exists():
        messages.warning(request,'You can only rate products you have purchased')
        return redirect('product_detail',slug=product.slug)
    try:
        rating = models.Rating.objects.get(product=product,user=request.user)
    except models.Rating.DoesNotExists:
        rating =None
    if request.method=='POST':
        form = RatingForms(request.POST,instance=rating)
        if form.is_valid():
            rating = form.save(commit=False)
            rating.product = product
            rating.user=request.user
            rating.save()
            return redirect('product_detail')
    else:
        form = RatingForms(instance=rating)
    return render(request,'shop/rate_product.html',{
        'form':form,
        'product':product,
    })

def login_view(request):
    form = AuthenticationForm(request, data=request.POST or None)

    if request.method == "POST":
        if form.is_valid():  
            user = form.get_user()
            login(request, user)
            return redirect("home")
        else:
            messages.error(request, "Invalid username or password")
            return redirect('register')

    return render(request, "shop/login.html", {"form": form})



#alternative login er khetre amr manually HTML file make korte hobe
'''

def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect("home")
        else:
            messages.error(request, "Invalid username or password")

    return render(request, "shop/login.html")

'''
def register_view(request):
    if request.method =='POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request,user)
            messages.success(request,'Registration Successful!')
            return redirect('home')
    else:
        form = RegistrationForm()
    return render(request,'shop/register.html', {'form':form})

def logout_view(request):
    logout(request)
    return redirect('home')


       